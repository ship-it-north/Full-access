"""Tests de la couche validation : sélection, folds, Monte Carlo, DSR, verdict.

Le verdict final est du code comme le reste : il est testé sur des cas où la
réponse est connue, y compris le cas « tous les critères échouent ».
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validation as V  # noqa: E402
from ensemble import EnsembleConfig, EnsembleResult  # noqa: E402
from main_ensemble import recommendation  # noqa: E402


def _result(daily_returns: pd.Series) -> EnsembleResult:
    return EnsembleResult(EnsembleConfig(), pd.DataFrame(), pd.Series(dtype=float), daily_returns)


def _returns(mean, std, n=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC")
    return pd.Series(rng.normal(mean, std, n), index=idx)


# --------------------------------------------------------------------------- #
# Règle de sélection
# --------------------------------------------------------------------------- #
def test_selection_rejette_les_sharpe_insuffisants():
    results = {"A": _result(_returns(-0.001, 0.01)), "B": _result(_returns(0.0, 0.01, seed=1))}
    kept, log = V.select_components(results, min_sharpe=0.3)
    assert kept == []
    assert all("rejeté" in line for line in log)


def test_selection_garde_un_signal_fort_et_decorrele():
    base = _returns(0.002, 0.01, seed=2)
    independant = _returns(0.002, 0.01, seed=99)
    results = {"A": _result(base), "B": _result(independant)}
    kept, _ = V.select_components(results, min_sharpe=0.3, max_corr=0.6)
    assert set(kept) == {"A", "B"}


def test_selection_rejette_un_signal_trop_correle():
    base = _returns(0.002, 0.01, seed=3)
    clone = base * 1.01 + 1e-6  # corrélation ~1
    results = {"A": _result(base), "B": _result(clone)}
    kept, log = V.select_components(results, min_sharpe=0.3, max_corr=0.6)
    assert len(kept) == 1
    assert any("corr" in line for line in log)


# --------------------------------------------------------------------------- #
# Découpage walk-forward
# --------------------------------------------------------------------------- #
def test_folds_train_et_test_ne_se_chevauchent_pas():
    idx = pd.date_range("2023-01-01", "2026-01-01", freq="1h", tz="UTC")
    folds = V.make_folds(idx, train_months=12, test_months=3, step_months=3)
    assert len(folds) > 4
    for f in folds:
        assert f.train_end == f.test_start          # aucune barre partagée
        assert f.train_start < f.train_end < f.test_end
    # les fenêtres de test se suivent sans trou ni recouvrement
    for a, b in zip(folds, folds[1:]):
        assert b.test_start >= a.test_start
        assert b.train_start > a.train_start


def test_folds_avancent_de_3_mois():
    idx = pd.date_range("2023-01-01", "2026-01-01", freq="1h", tz="UTC")
    folds = V.make_folds(idx)
    deltas = {(b.train_start - a.train_start).days for a, b in zip(folds, folds[1:])}
    assert all(85 <= d <= 95 for d in deltas)


# --------------------------------------------------------------------------- #
# Monte Carlo
# --------------------------------------------------------------------------- #
def _trades(rets):
    equity, rows = 100.0, []
    for r in rets:
        pnl = equity * r
        equity += pnl
        rows.append({"net_pnl": pnl, "equity_after": equity})
    return pd.DataFrame(rows)


def test_monte_carlo_percentiles_ordonnes():
    rng = np.random.default_rng(4)
    mc = V.monte_carlo(_trades(rng.normal(0.01, 0.05, 80)), n_runs=300, seed=1)
    assert mc["rendement_p5"] < mc["rendement_median"] < mc["rendement_p95"]
    assert 0.0 <= mc["proba_perte"] <= 1.0
    assert mc["maxdd_median"] <= 0


def test_monte_carlo_sur_serie_perdante_donne_proba_perte_elevee():
    mc = V.monte_carlo(_trades([-0.02] * 50), n_runs=200, seed=2)
    assert mc["proba_perte"] == 1.0
    assert mc["rendement_p5"] < 0


def test_monte_carlo_vide_si_trop_peu_de_trades():
    assert V.monte_carlo(_trades([0.01, -0.01]), n_runs=10) == {}


# --------------------------------------------------------------------------- #
# Deflated Sharpe Ratio
# --------------------------------------------------------------------------- #
def test_dsr_diminue_quand_le_nombre_dessais_augmente():
    rets = _returns(0.002, 0.01, n=800, seed=5)
    trials = list(np.random.default_rng(6).normal(0.5, 0.5, 50))
    petit = V.deflated_sharpe(rets, 5, trials)["deflated_sharpe_ratio"]
    grand = V.deflated_sharpe(rets, 5000, trials)["deflated_sharpe_ratio"]
    assert grand < petit


def test_dsr_seuil_hasard_nul_sans_variance_dessais():
    rets = _returns(0.002, 0.01, n=800, seed=7)
    out = V.deflated_sharpe(rets, 10, [1.0])
    assert out["sharpe_seuil_hasard_annualise"] == pytest.approx(0.0)


def test_dsr_proche_de_1_pour_une_strategie_tres_forte_peu_cherchee():
    rets = _returns(0.004, 0.005, n=800, seed=8)  # Sharpe quotidien très élevé
    out = V.deflated_sharpe(rets, 2, [0.5, 0.6])
    assert out["deflated_sharpe_ratio"] > 0.95


# --------------------------------------------------------------------------- #
# Benchmark
# --------------------------------------------------------------------------- #
def test_buy_and_hold_suit_le_prix():
    idx = pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC")
    close = pd.Series(np.linspace(100, 200, 100), index=idx)
    eq = V.buy_and_hold(close, 100.0)
    assert eq.iloc[0] == pytest.approx(100.0)
    assert eq.iloc[-1] == pytest.approx(200.0)


def test_curve_metrics_sur_drawdown_connu():
    idx = pd.date_range("2023-01-01", periods=4, freq="365D", tz="UTC")
    eq = pd.Series([100.0, 200.0, 100.0, 150.0], index=idx)
    m = V.curve_metrics(eq, "test")
    assert m["max_drawdown"] == pytest.approx(-0.5)
    assert m["rendement_total"] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Verdict final
# --------------------------------------------------------------------------- #
def _contexte(kept, sys_sharpe, btc_sharpe, dsr, p5, worst_sens, n_trades):
    p1 = {
        "kept": kept,
        "table": pd.DataFrame([
            {"strategie": "S1", "periode": "out-of-sample", "sharpe": sys_sharpe},
        ]),
    }
    p3 = {
        "benchmark": pd.DataFrame([{"sharpe": sys_sharpe}, {"sharpe": btc_sharpe}]),
        "dsr": {"deflated_sharpe_ratio": dsr, "n_configurations": 100,
                "sharpe_seuil_hasard_annualise": 1.5},
        "mc": {"rendement_p5": p5, "proba_perte": 0.2},
        "sensitivity": pd.DataFrame({"-30%": [worst_sens], "base": [1.0], "+30%": [1.0]},
                                    index=["atr_stop_mult"]),
        "trades": pd.DataFrame(index=range(n_trades)),
    }
    return p1, p3


def test_verdict_ne_pas_deployer_si_tout_echoue():
    p1, p3 = _contexte([], -0.35, 0.71, 0.001, -0.21, -0.2, 44)
    lines = recommendation(p1, p3, pd.DataFrame(), beats_btc=False)
    texte = "\n".join(lines)
    assert "NE PAS DÉPLOYER" in texte
    assert "0/6" in texte
    assert texte.count("| NON |") == 6


def test_verdict_deployer_seulement_si_tous_les_criteres_passent():
    p1, p3 = _contexte(["S1"], 1.2, 0.71, 0.99, 0.15, 0.8, 250)
    lines = recommendation(p1, p3, pd.DataFrame(), beats_btc=True)
    texte = "\n".join(lines)
    assert "**Recommandation : DÉPLOYER**" in texte
    assert "6/6" in texte
    assert "| NON |" not in texte


def test_verdict_un_seul_critere_manquant_suffit_a_bloquer():
    p1, p3 = _contexte(["S1"], 1.2, 0.71, 0.99, 0.15, 0.8, 42)  # trop peu de trades
    texte = "\n".join(recommendation(p1, p3, pd.DataFrame(), beats_btc=True))
    assert "NE PAS DÉPLOYER" in texte
    assert "5/6" in texte
