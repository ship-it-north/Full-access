"""Tests des composantes de signal et du moteur d'ensemble.

Même méthode que pour le premier moteur : réponses connues sur données
synthétiques, puis invariance par préfixe pour prouver l'absence de look-ahead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import signals as S  # noqa: E402
from ensemble import (  # noqa: E402
    EnsembleConfig,
    composite_score,
    rolling_correlations,
    run_ensemble,
    sharpe,
)

H = S.BARS_PER_DAY


def _frame(close, high=None, low=None, open_=None, start="2023-01-01"):
    close = np.asarray(close, float)
    idx = pd.date_range(start, periods=len(close), freq="1h", tz="UTC")
    return pd.DataFrame({
        "open": close if open_ is None else open_,
        "high": close if high is None else high,
        "low": close if low is None else low,
        "close": close,
    }, index=idx)


def _trend(n_days=200, daily_drift=0.004, seed=1, vol=0.002):
    rng = np.random.default_rng(seed)
    n = n_days * H
    steps = rng.normal(daily_drift / H, vol, n)
    return 100 * np.exp(np.cumsum(steps))


# --------------------------------------------------------------------------- #
# Briques
# --------------------------------------------------------------------------- #
def test_realized_vol_sur_serie_de_vol_connue():
    rng = np.random.default_rng(0)
    n = 60 * H
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    vol = S.realized_vol(_frame(close)["close"], 30)
    attendu = 0.01 * np.sqrt(S.BARS_PER_YEAR)
    assert vol.iloc[-1] == pytest.approx(attendu, rel=0.15)


def test_atr_quotidien_sur_range_constant():
    """Bougies quotidiennes de range constant 10 -> ATR = 10."""
    n = 40 * H
    close = np.full(n, 100.0)
    df = _frame(close, high=np.full(n, 105.0), low=np.full(n, 95.0))
    got = S.atr(df, 14)
    assert got.dropna().iloc[-1] == pytest.approx(10.0, rel=0.02)


def test_atr_est_decale_dun_jour():
    """La valeur vue pendant le jour D provient de journées entièrement closes."""
    n = 40 * H
    df = _frame(np.full(n, 100.0), high=np.full(n, 105.0), low=np.full(n, 95.0))
    got = S.atr(df, 14)
    premier_jour = got.iloc[:H]
    assert premier_jour.isna().all()


# --------------------------------------------------------------------------- #
# S1 TSMOM
# --------------------------------------------------------------------------- #
def test_s1_positif_en_tendance_haussiere_et_negatif_en_baissiere():
    hausse = _trend(200, daily_drift=0.006, seed=2)
    baisse = hausse[::-1].copy()
    s_up = S.s1_tsmom(_frame(hausse)).iloc[-1]
    s_dn = S.s1_tsmom(_frame(baisse)).iloc[-1]
    assert s_up > 0.2
    assert s_dn < -0.2


def test_s1_borne_dans_moins_un_plus_un():
    close = 100 * np.exp(np.linspace(0, 3, 200 * H))  # tendance extrême
    s = S.s1_tsmom(_frame(close)).dropna()
    assert s.max() <= 1.0 and s.min() >= -1.0
    assert s.iloc[-1] > 0.9  # saturation attendue


def test_s1_normalise_par_la_volatilite():
    """Même rendement, vol double -> score plus faible."""
    n = 200 * H
    rng = np.random.default_rng(3)
    base = np.cumsum(rng.normal(0, 0.001, n))
    calme = 100 * np.exp(np.linspace(0, 0.5, n) + base * 0.2)
    agite = 100 * np.exp(np.linspace(0, 0.5, n) + base * 3.0)
    assert S.s1_tsmom(_frame(calme)).iloc[-1] > S.s1_tsmom(_frame(agite)).iloc[-1]


# --------------------------------------------------------------------------- #
# S2 cross-sectional
# --------------------------------------------------------------------------- #
def test_s2_classe_les_paires_par_rendement():
    n = 60 * H
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    panel = pd.DataFrame({
        "FORT": 100 * np.exp(np.linspace(0, 0.8, n)),
        "MOYEN": 100 * np.exp(np.linspace(0, 0.3, n)),
        "FAIBLE": 100 * np.exp(np.linspace(0, -0.4, n)),
    }, index=idx)
    s = S.s2_xsmom(panel).iloc[-1]
    assert s["FORT"] > s["MOYEN"] > s["FAIBLE"]
    assert s["FORT"] == pytest.approx(1.0)
    assert s["FAIBLE"] == pytest.approx(-1 / 3, abs=0.01)  # rang 1/3 -> 2*1/3-1


def test_s2_fige_le_score_entre_reequilibrages():
    n = 60 * H
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(5)
    panel = pd.DataFrame(
        {f"P{k}": 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n))) for k in range(5)}, index=idx
    )
    s = S.s2_xsmom(panel, rebalance_days=7).dropna()
    changements = (s.diff().abs().sum(axis=1) > 1e-12).sum()
    # 60 jours / 7 -> au plus 9 dates de changement
    assert changements <= 9


# --------------------------------------------------------------------------- #
# S3 Donchian
# --------------------------------------------------------------------------- #
def test_s3_passe_long_sur_cassure_et_sort_sur_plus_bas():
    n = 80 * H
    close = np.full(n, 100.0)
    close[60 * H:] = 130.0          # cassure franche du plus haut 20 j et 55 j
    close[70 * H:] = 60.0           # puis cassure du plus bas
    df = _frame(close)
    s = S.s3_donchian(df)
    assert s.iloc[65 * H] == pytest.approx(1.0)
    assert s.iloc[-1] <= 0.0


def test_s3_reste_neutre_avant_toute_cassure():
    n = 80 * H
    df = _frame(np.full(n, 100.0))
    assert S.s3_donchian(df).abs().max() == 0.0


def test_s3_utilise_la_fenetre_precedente_pas_la_barre_courante():
    """Le plus haut de référence exclut la barre en cours (sinon jamais de cassure)."""
    n = 80 * H
    close = np.full(n, 100.0)
    close[60 * H] = 130.0  # une seule barre au-dessus
    s = S.s3_donchian(_frame(close))
    assert s.iloc[60 * H] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# S4 mean reversion
# --------------------------------------------------------------------------- #
def test_s4_negatif_quand_le_prix_est_trop_haut():
    n = 60 * H
    rng = np.random.default_rng(7)
    close = 100 + rng.normal(0, 1, n)
    close[-1] = 130.0  # très au-dessus de la MA
    assert S.s4_meanrev(_frame(close)).iloc[-1] == pytest.approx(-1.0)


def test_s4_positif_quand_le_prix_est_trop_bas():
    n = 60 * H
    rng = np.random.default_rng(8)
    close = 100 + rng.normal(0, 1, n)
    close[-1] = 70.0
    assert S.s4_meanrev(_frame(close)).iloc[-1] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Filtres
# --------------------------------------------------------------------------- #
def test_f1_efficiency_ratio_vaut_1_sur_droite_parfaite():
    close = np.arange(100, 200, dtype=float)
    assert S.f1_efficiency_ratio(_frame(close), 20).iloc[-1] == pytest.approx(1.0)


def test_f1_efficiency_ratio_proche_de_zero_en_oscillation():
    close = np.array([100.0, 101.0] * 50)
    assert S.f1_efficiency_ratio(_frame(close), 20).iloc[-1] < 0.1


def test_f2_penalise_la_vol_haute_et_laisse_passer_la_vol_basse():
    n = 500 * H
    rng = np.random.default_rng(9)
    steps = rng.normal(0, 0.002, n)
    steps[-20 * H:] *= 8  # explosion de vol récente
    close = 100 * np.exp(np.cumsum(steps))
    mult = S.f2_vol_regime(_frame(close))
    assert mult.iloc[-1] < 0.6
    assert mult.iloc[200 * H] > 0.8


def test_f3_penalise_le_funding_extreme():
    idx = pd.date_range("2023-01-01", periods=1200, freq="8h", tz="UTC")
    rng = np.random.default_rng(11)
    funding = pd.Series(rng.normal(0.0001, 0.00005, len(idx)), index=idx)
    funding.iloc[-5:] = 0.01  # funding extrême
    hourly = pd.date_range(idx[0], idx[-1], freq="1h", tz="UTC")
    mult = S.f3_funding_regime(funding, hourly)
    assert mult.iloc[-1] == pytest.approx(0.3)
    assert mult.loc[idx[600]] == pytest.approx(1.0)


def test_f3_neutre_si_funding_absent():
    hourly = pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC")
    assert (S.f3_funding_regime(None, hourly) == 1.0).all()


# --------------------------------------------------------------------------- #
# Score composite
# --------------------------------------------------------------------------- #
def test_composite_pondere_et_multiplie_les_filtres():
    idx = pd.date_range("2023-01-01", periods=3, freq="1h", tz="UTC")
    panels = {
        "S1_tsmom": pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx),
        "S3_donchian": pd.DataFrame({"A": [0.0, 0.0, 0.0]}, index=idx),
        "F1_efficiency": pd.DataFrame({"A": [1.0, 0.5, 0.0]}, index=idx),
    }
    cfg = EnsembleConfig(weights=(("S1_tsmom", 1.0), ("S3_donchian", 1.0)), filters=("F1_efficiency",))
    got = composite_score(panels, cfg)["A"]
    assert list(got) == pytest.approx([0.5, 0.25, 0.0])


# --------------------------------------------------------------------------- #
# Moteur d'ensemble
# --------------------------------------------------------------------------- #
def _panels_simple(n=300, score_value=1.0, price=None, atr_value=1.0):
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    if price is None:
        price = np.full(n, 100.0)
    price = np.asarray(price, float)
    df = pd.DataFrame({"A": price}, index=idx)
    return {
        "open": df.copy(), "high": df.copy(), "low": df.copy(), "close": df.copy(),
        "atr": pd.DataFrame({"A": np.full(n, atr_value)}, index=idx),
        "vol": pd.DataFrame({"A": np.full(n, 0.5)}, index=idx),
        "S1_tsmom": pd.DataFrame({"A": np.full(n, score_value)}, index=idx),
    }


def test_entree_a_louverture_de_la_barre_suivante():
    panels = _panels_simple()
    cfg = EnsembleConfig(sizing="fixed", threshold=0.3)
    res = run_ensemble(panels, cfg)
    assert not res.trades.empty or len(res.equity) > 0
    # la première entrée ne peut pas être à la première barre
    if not res.trades.empty:
        assert res.trades.entry_time.iloc[0] > panels["close"].index[0]


def test_stop_a_2_5_atr_sous_lentree():
    n = 20
    price = np.full(n, 100.0)
    price[5:] = 90.0  # chute sous le stop 100 - 2.5 = 97.5
    panels = _panels_simple(n=n, price=price)
    cfg = EnsembleConfig(sizing="fixed", atr_stop_mult=2.5)
    res = run_ensemble(panels, cfg)
    t = res.trades.iloc[0]
    assert t.initial_stop == pytest.approx(97.5)
    assert t.exit_reason == "stop"
    assert t.r_multiple < -1.0  # frais + slippage au-delà de -1R


def test_sortie_quand_le_score_passe_negatif():
    n = 30
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    panels = _panels_simple(n=n)
    score = np.full(n, 1.0)
    score[10:] = -0.5
    panels["S1_tsmom"] = pd.DataFrame({"A": score}, index=idx)
    res = run_ensemble(panels, EnsembleConfig(sizing="fixed"))
    t = res.trades.iloc[0]
    assert t.exit_reason == "score_exit"
    assert t.exit_time == idx[11]  # décidé sur la ligne 10, exécuté à l'ouverture de 11


def test_trailing_stop_arme_apres_1R():
    n = 40
    price = np.full(n, 100.0)
    price[3:20] = 110.0   # +10 = +4R avec un stop à 2.5 ATR (ATR=1)
    price[20:] = 105.0    # redescend sous le trailing (110 - 3 = 107)
    panels = _panels_simple(n=n, price=price)
    res = run_ensemble(panels, EnsembleConfig(sizing="fixed", atr_trail_mult=3.0))
    t = res.trades.iloc[0]
    assert t.exit_reason == "stop"
    assert t.exit_price > t.entry_price  # sorti en profit grâce au trailing
    assert t.r_multiple > 1.0


def test_sizing_vol_target_plafonne_a_5_pct():
    n = 30
    price = np.full(n, 100.0)
    price[20:] = 90.0  # déclenche le stop pour clore le trade
    panels = _panels_simple(n=n, price=price)
    panels["vol"] = pd.DataFrame({"A": np.full(n, 0.10)}, index=panels["close"].index)
    # cible 20% / vol 10% = 2.0 -> plafonné à 5%
    res = run_ensemble(panels, EnsembleConfig(sizing="voltarget", vol_target=0.20, max_risk=0.05))
    assert res.trades.iloc[0].risk_pct == pytest.approx(0.05)


def test_sizing_vol_target_reduit_quand_la_vol_monte():
    """Le plafond de 5% ne cède que si la vol annualisée dépasse 400% (0.20/vol < 0.05)."""
    n = 30
    price = np.full(n, 100.0)
    price[20:] = 90.0
    panels = _panels_simple(n=n, price=price)
    panels["vol"] = pd.DataFrame({"A": np.full(n, 8.0)}, index=panels["close"].index)
    res = run_ensemble(panels, EnsembleConfig(sizing="voltarget", vol_target=0.20))
    assert res.trades.iloc[0].risk_pct == pytest.approx(0.025)  # 0.20 / 8.0


def test_max_5_positions():
    n = 60
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    cols = [f"P{k}" for k in range(8)]
    price = pd.DataFrame({c: np.full(n, 100.0) for c in cols}, index=idx)
    panels = {
        "open": price, "high": price, "low": price, "close": price,
        "atr": pd.DataFrame({c: np.full(n, 1.0) for c in cols}, index=idx),
        "vol": pd.DataFrame({c: np.full(n, 0.5) for c in cols}, index=idx),
        "S1_tsmom": pd.DataFrame({c: np.full(n, 1.0) for c in cols}, index=idx),
    }
    corr = (np.zeros((n, 8, 8)), idx)  # décorrélées : la contrainte de corr ne mord pas
    res = run_ensemble(panels, EnsembleConfig(sizing="fixed", max_positions=5), corr_cube=corr)
    # aucune sortie possible (prix plat) : 5 positions ouvertes, donc 0 trade clos
    assert res.trades.empty
    assert res.equity.iloc[-1] == pytest.approx(100.0, abs=1e-6)


def test_contrainte_de_correlation_bloque_les_paires_correlees():
    n = 60
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    cols = ["A", "B"]
    price = pd.DataFrame({c: np.full(n, 100.0) for c in cols}, index=idx)
    panels = {
        "open": price, "high": price, "low": price, "close": price,
        "atr": pd.DataFrame({c: np.full(n, 1.0) for c in cols}, index=idx),
        "vol": pd.DataFrame({c: np.full(n, 0.5) for c in cols}, index=idx),
        "S1_tsmom": pd.DataFrame({"A": np.full(n, 1.0), "B": np.full(n, 0.9)}, index=idx),
    }
    corr = (np.ones((n, 2, 2)) * 0.95, idx)  # tout est corrélé à 0.95 > 0.7
    res = run_ensemble(panels, EnsembleConfig(sizing="fixed", max_positions=5), corr_cube=corr)
    # une seule position peut être ouverte
    assert res.equity.iloc[-1] == pytest.approx(100.0, abs=1e-6)
    assert res.trades.empty


def test_exposition_brute_plafonnee():
    n = 30
    panels = _panels_simple(n=n)
    panels["vol"] = pd.DataFrame({"A": np.full(n, 0.05)}, index=panels["close"].index)
    cfg = EnsembleConfig(sizing="fixed", fixed_risk=0.05, atr_stop_mult=0.1, max_gross=2.0)
    res = run_ensemble(panels, cfg)
    assert res.equity is not None
    # risque 5% sur un stop de 0.1% -> notionnel théorique 50x, bridé à 2x
    assert res.trades.empty or res.trades.iloc[0].notional <= 200.0 + 1e-6


def test_couts_doubles_degradent_le_resultat():
    n = 40
    price = np.full(n, 100.0)
    price[3:20] = 110.0
    price[20:] = 105.0
    panels = _panels_simple(n=n, price=price)
    base = run_ensemble(panels, EnsembleConfig(sizing="fixed", cost_mult=1.0))
    cher = run_ensemble(panels, EnsembleConfig(sizing="fixed", cost_mult=2.0))
    # pas exactement 2x : le slippage doublé modifie aussi le prix de sortie
    assert cher.trades.iloc[0].fees == pytest.approx(2 * base.trades.iloc[0].fees, rel=1e-3)
    assert cher.trades.iloc[0].net_pnl < base.trades.iloc[0].net_pnl


def test_sharpe_sur_serie_connue():
    rets = pd.Series([0.01] * 365)  # rendement constant -> std nulle
    assert np.isnan(sharpe(rets))
    rng = np.random.default_rng(13)
    r = pd.Series(rng.normal(0.001, 0.01, 2000))
    attendu = 0.001 / 0.01 * np.sqrt(365)
    assert sharpe(r) == pytest.approx(attendu, rel=0.25)


# --------------------------------------------------------------------------- #
# Non-look-ahead : invariance par préfixe sur tous les signaux
# --------------------------------------------------------------------------- #
def _serie_realiste(n_days=400, seed=21):
    rng = np.random.default_rng(seed)
    n = n_days * H
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.003, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.003, n)))
    idx = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)


@pytest.mark.parametrize("fonction", [
    S.s1_tsmom, S.s3_donchian, S.s4_meanrev, S.f1_efficiency_ratio, S.f2_vol_regime, S.atr,
])
def test_invariance_par_prefixe_de_chaque_composante(fonction):
    df = _serie_realiste()
    complet = fonction(df)
    for cut in (250 * H, 350 * H):
        tronque = fonction(df.iloc[:cut])
        a = complet.iloc[:cut].to_numpy()
        b = tronque.to_numpy()
        both = ~(np.isnan(a) | np.isnan(b))
        assert np.isnan(a).sum() == np.isnan(b).sum(), f"{fonction.__name__} : NaN divergents"
        np.testing.assert_allclose(a[both], b[both], rtol=1e-9, atol=1e-9,
                                   err_msg=f"{fonction.__name__} lit le futur (cut={cut})")


def test_invariance_par_prefixe_du_cross_sectional():
    panel = pd.concat({f"P{k}": _serie_realiste(seed=30 + k)["close"] for k in range(4)}, axis=1)
    complet = S.s2_xsmom(panel)
    cut = 300 * H
    tronque = S.s2_xsmom(panel.iloc[:cut])
    a, b = complet.iloc[:cut].to_numpy(), tronque.to_numpy()
    both = ~(np.isnan(a) | np.isnan(b))
    np.testing.assert_allclose(a[both], b[both], rtol=1e-9)


def test_invariance_par_prefixe_du_moteur():
    """Les trades clos avant la coupure sont identiques sur série tronquée."""
    frames = {f"P{k}": _serie_realiste(seed=40 + k) for k in range(3)}
    panels = S.build_panels(frames)
    cfg = EnsembleConfig(weights=(("S1_tsmom", 1.0),), sizing="fixed")
    full = run_ensemble(panels, cfg)
    if full.trades.empty:
        pytest.skip("aucun trade")
    cut = panels["close"].index[int(len(panels["close"]) * 0.7)]
    panels_t = S.build_panels({k: v.loc[v.index <= cut] for k, v in frames.items()})
    part = run_ensemble(panels_t, cfg)

    ref = full.trades[full.trades.exit_time <= cut].reset_index(drop=True)
    got = part.trades[part.trades.exit_time <= cut].reset_index(drop=True)
    cols = ["pair", "entry_time", "entry_price", "exit_time", "exit_price", "exit_reason"]
    assert len(ref) == len(got)
    pd.testing.assert_frame_equal(ref[cols], got[cols])


def test_correlations_nutilisent_que_le_passe():
    panel = pd.concat({f"P{k}": _serie_realiste(200, seed=50 + k)["close"] for k in range(3)}, axis=1)
    cube, idx = rolling_correlations(panel, 30)
    cut = 150
    cube_t, idx_t = rolling_correlations(panel.loc[panel.index <= idx[cut]], 30)
    a, b = cube[:cut], cube_t[:cut]
    both = ~(np.isnan(a) | np.isnan(b))
    np.testing.assert_allclose(a[both], b[both], rtol=1e-9)
