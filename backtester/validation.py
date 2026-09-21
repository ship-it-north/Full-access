"""Phase 3 — validation : walk-forward, benchmark, Monte Carlo, DSR, sensibilités.

Principe directeur : aucune décision (sélection de composantes, seuil) n'est
prise sur une donnée qui appartient à une fenêtre de test. Chaque fold
sélectionne sur ses 12 mois d'entraînement et n'est évalué que sur les 3 mois
suivants, jamais vus.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

import signals as S
from ensemble import (
    RUN_COUNTER,
    EnsembleConfig,
    EnsembleResult,
    max_drawdown,
    metrics,
    run_ensemble,
    sharpe,
)

EULER_GAMMA = 0.5772156649015329
DAYS_PER_YEAR = 365

# Sharpe de chaque configuration évaluée : alimente la variance des essais du DSR.
TRIAL_SHARPES: list[float] = []


def record_trial(value: float) -> None:
    if value is not None and np.isfinite(value):
        TRIAL_SHARPES.append(float(value))


# --------------------------------------------------------------------------- #
# Phase 1 — composantes isolées et règle de sélection
# --------------------------------------------------------------------------- #
def component_config(name: str, **kwargs) -> EnsembleConfig:
    """Une composante seule = ensemble à un signal, sans filtre, sizing fixe 2%."""
    defaults = dict(
        weights=((name, 1.0),), filters=(), threshold=0.3,
        sizing="fixed", fixed_risk=0.02, label=name,
    )
    defaults.update(kwargs)
    return EnsembleConfig(**defaults)


def run_components(
    panels: dict[str, pd.DataFrame],
    corr_cube,
    names: list[str],
    start=None,
    end=None,
    **cfg_kwargs,
) -> dict[str, EnsembleResult]:
    out = {}
    for name in names:
        res = run_ensemble(panels, component_config(name, **cfg_kwargs), corr_cube, start, end)
        record_trial(sharpe(res.daily_returns))
        out[name] = res
    return out


def correlation_matrix(results: dict[str, EnsembleResult]) -> pd.DataFrame:
    series = {k: v.daily_returns for k, v in results.items() if len(v.daily_returns) > 5}
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).corr()


def select_components(
    results: dict[str, EnsembleResult],
    min_sharpe: float = 0.3,
    max_corr: float = 0.6,
) -> tuple[list[str], list[str]]:
    """Sharpe > seuil ET corrélation < seuil avec les composantes déjà retenues.

    Retourne (retenues, journal des décisions). Ordre d'examen : Sharpe décroissant.
    """
    log: list[str] = []
    sharpes = {k: sharpe(v.daily_returns) for k, v in results.items()}
    corr = correlation_matrix(results)
    ranked = sorted(sharpes, key=lambda k: -(sharpes[k] if np.isfinite(sharpes[k]) else -9))

    kept: list[str] = []
    for name in ranked:
        sr = sharpes[name]
        if not np.isfinite(sr) or sr <= min_sharpe:
            log.append(f"{name}: rejeté (Sharpe {sr:.2f} <= {min_sharpe})")
            continue
        conflict = None
        for other in kept:
            if name in corr.index and other in corr.columns:
                rho = corr.loc[name, other]
                if np.isfinite(rho) and abs(rho) >= max_corr:
                    conflict = (other, rho)
                    break
        if conflict:
            log.append(f"{name}: rejeté (corr {conflict[1]:.2f} avec {conflict[0]} >= {max_corr})")
            continue
        kept.append(name)
        log.append(f"{name}: RETENU (Sharpe {sr:.2f})")
    return kept, log


# --------------------------------------------------------------------------- #
# Phase 3.1 — walk-forward glissant
# --------------------------------------------------------------------------- #
@dataclass
class Fold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    selected: list[str] = field(default_factory=list)
    threshold: float = np.nan
    train_sharpe: float = np.nan
    log: list[str] = field(default_factory=list)
    component_sharpes: dict = field(default_factory=dict)


def make_folds(index: pd.DatetimeIndex, train_months=12, test_months=3, step_months=3) -> list[Fold]:
    start, last = index[0], index[-1]
    folds = []
    t0 = start
    while True:
        train_end = t0 + pd.DateOffset(months=train_months)
        test_end = train_end + pd.DateOffset(months=test_months)
        if train_end >= last:
            break
        folds.append(Fold(t0, train_end, train_end, min(test_end, last)))
        t0 = t0 + pd.DateOffset(months=step_months)
    return folds


def walk_forward(
    panels: dict[str, pd.DataFrame],
    corr_cube,
    component_names: list[str],
    thresholds=(0.3, 0.5, 0.7),
    filters: tuple[str, ...] = ("F1_efficiency", "F2_volregime", "F3_funding"),
    base_config: dict | None = None,
    min_sharpe: float = 0.3,
    max_corr_sel: float = 0.6,
    initial_capital: float = 100.0,
    verbose: bool = True,
) -> tuple[pd.Series, pd.DataFrame, list[Fold]]:
    """Sélection sur le train, évaluation sur le test, équité concaténée."""
    base_config = base_config or {}
    folds = make_folds(panels["close"].index)
    equity_parts: list[pd.Series] = []
    trades_parts: list[pd.DataFrame] = []
    capital = initial_capital

    for fold in folds:
        comps = run_components(
            panels, corr_cube, component_names, fold.train_start, fold.train_end
        )
        kept, log = select_components(comps, min_sharpe, max_corr_sel)
        fold.selected, fold.log = kept, log
        fold.component_sharpes = {k: sharpe(v.daily_returns) for k, v in comps.items()}
        if not kept:
            if verbose:
                print(f"  {fold.test_start.date()} -> {fold.test_end.date()} : "
                      f"aucune composante retenue, hors marché")
            idx = panels["close"].loc[fold.test_start:fold.test_end].index
            equity_parts.append(pd.Series(capital, index=idx))
            continue

        weights = tuple((name, 1.0) for name in kept)
        best, best_sharpe = None, -np.inf
        for th in thresholds:
            cfg = EnsembleConfig(weights=weights, filters=filters, threshold=th,
                                 initial_capital=capital, **base_config)
            res = run_ensemble(panels, cfg, corr_cube, fold.train_start, fold.train_end)
            sr = sharpe(res.daily_returns)
            record_trial(sr)
            if np.isfinite(sr) and sr > best_sharpe:
                best, best_sharpe = th, sr
        if best is None:
            best, best_sharpe = thresholds[0], np.nan
        fold.threshold, fold.train_sharpe = best, best_sharpe

        cfg = EnsembleConfig(weights=weights, filters=filters, threshold=best,
                             initial_capital=capital, **base_config)
        test = run_ensemble(panels, cfg, corr_cube, fold.test_start, fold.test_end)
        if len(test.equity):
            equity_parts.append(test.equity)
            capital = float(test.equity.iloc[-1])
        if not test.trades.empty:
            t = test.trades.copy()
            t["fold"] = str(fold.test_start.date())
            trades_parts.append(t)
        if verbose:
            print(f"  {fold.test_start.date()} -> {fold.test_end.date()} : "
                  f"{'+'.join(kept)} seuil {best} | train SR {best_sharpe:.2f} | "
                  f"capital {capital:.1f}")

    equity = pd.concat(equity_parts).sort_index() if equity_parts else pd.Series(dtype=float)
    equity = equity[~equity.index.duplicated(keep="last")]
    trades = pd.concat(trades_parts, ignore_index=True) if trades_parts else pd.DataFrame()
    return equity, trades, folds


# --------------------------------------------------------------------------- #
# Phase 3.2 — benchmark buy & hold
# --------------------------------------------------------------------------- #
def buy_and_hold(close: pd.Series, initial_capital: float = 100.0) -> pd.Series:
    close = close.dropna()
    if close.empty:
        return pd.Series(dtype=float)
    return initial_capital * close / close.iloc[0]


def curve_metrics(equity: pd.Series, label: str) -> dict:
    if equity.empty:
        return {"strategie": label, "sharpe": np.nan, "rendement_total": np.nan,
                "max_drawdown": np.nan, "vol_annualisee": np.nan, "calmar": np.nan}
    daily = equity.resample("1D").last().dropna()
    rets = daily.pct_change().dropna()
    total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    dd = max_drawdown(equity)
    return {
        "strategie": label,
        "sharpe": sharpe(rets),
        "rendement_total": total,
        "cagr": float(cagr),
        "vol_annualisee": float(rets.std() * np.sqrt(DAYS_PER_YEAR)),
        "max_drawdown": dd,
        "calmar": float(cagr / abs(dd)) if dd < 0 else np.nan,
    }


# --------------------------------------------------------------------------- #
# Phase 3.3 — Monte Carlo sur la séquence de trades
# --------------------------------------------------------------------------- #
def monte_carlo(trades: pd.DataFrame, n_runs: int = 1000, seed: int = 0) -> dict:
    """Rééchantillonne la séquence de trades (bootstrap) et compose les rendements."""
    if trades.empty:
        return {}
    equity_before = trades["equity_after"] - trades["net_pnl"]
    rets = (trades["net_pnl"] / equity_before).to_numpy()
    rets = rets[np.isfinite(rets)]
    if len(rets) < 5:
        return {}
    rng = np.random.default_rng(seed)
    finals, drawdowns = np.empty(n_runs), np.empty(n_runs)
    for k in range(n_runs):
        sample = rng.choice(rets, size=len(rets), replace=True)
        curve = np.cumprod(1.0 + sample)
        finals[k] = curve[-1] - 1.0
        peak = np.maximum.accumulate(np.concatenate([[1.0], curve]))
        drawdowns[k] = (np.concatenate([[1.0], curve]) / peak - 1.0).min()
    return {
        "runs": n_runs,
        "trades_par_run": len(rets),
        "rendement_p5": float(np.percentile(finals, 5)),
        "rendement_median": float(np.median(finals)),
        "rendement_p95": float(np.percentile(finals, 95)),
        "rendement_moyen": float(finals.mean()),
        "maxdd_p5": float(np.percentile(drawdowns, 5)),
        "maxdd_median": float(np.median(drawdowns)),
        "proba_perte": float((finals < 0).mean()),
        "proba_ruine_80pct": float((drawdowns < -0.8).mean()),
        "finals": finals,
    }


# --------------------------------------------------------------------------- #
# Phase 3.4 — Deflated Sharpe Ratio (Bailey & López de Prado)
# --------------------------------------------------------------------------- #
def deflated_sharpe(daily_returns: pd.Series, n_trials: int, trial_sharpes: list[float]) -> dict:
    """DSR : probabilité que le Sharpe observé dépasse celui attendu par pur hasard.

    Toutes les grandeurs sont en unités quotidiennes ; les Sharpe des essais sont
    dé-annualisés pour estimer la variance des essais.
    """
    r = daily_returns.dropna()
    if len(r) < 30 or r.std() == 0:
        return {}
    sr = float(r.mean() / r.std())              # quotidien
    t = len(r)
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))

    trials = np.array([s for s in trial_sharpes if np.isfinite(s)]) / np.sqrt(DAYS_PER_YEAR)
    var_trials = float(trials.var(ddof=1)) if len(trials) > 1 else 0.0
    n = max(int(n_trials), 1)
    if var_trials > 0 and n > 1:
        z1 = stats.norm.ppf(1 - 1.0 / n)
        z2 = stats.norm.ppf(1 - 1.0 / (n * np.e))
        sr0 = np.sqrt(var_trials) * ((1 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)
    else:
        sr0 = 0.0

    denom = np.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr**2, 1e-12))
    dsr = float(stats.norm.cdf((sr - sr0) * np.sqrt(t - 1) / denom))
    return {
        "sharpe_annualise": sr * np.sqrt(DAYS_PER_YEAR),
        "sharpe_quotidien": sr,
        "sharpe_seuil_hasard_annualise": float(sr0 * np.sqrt(DAYS_PER_YEAR)),
        "n_configurations": n,
        "variance_essais": var_trials,
        "skewness": skew,
        "kurtosis": kurt,
        "observations": t,
        "deflated_sharpe_ratio": dsr,
    }


# --------------------------------------------------------------------------- #
# Phase 3.5 / 3.6 — sensibilités
# --------------------------------------------------------------------------- #
SENSITIVITY_PARAMS = {
    "atr_stop_mult": 2.5,
    "atr_trail_mult": 3.0,
    "vol_target": 0.20,
    "max_risk": 0.05,
    "max_corr": 0.7,
    "max_gross": 2.0,
}
SIGNAL_PARAMS = {
    "tsmom_horizons": (30, 60, 90),
    "xsmom_days": 28,
    "donchian_fast": (20, 10),
    "donchian_slow": (55, 20),
    "meanrev_days": 20,
    "er_bars": 20,
}


def scale_param(value, factor: float):
    if isinstance(value, tuple):
        return tuple(max(1, int(round(v * factor))) for v in value)
    if isinstance(value, int) and not isinstance(value, bool):
        return max(1, int(round(value * factor)))
    return value * factor


def exposure_stats(trades: pd.DataFrame, equity: pd.Series) -> dict:
    """Temps réellement passé en position et concentration du P&L dans le temps."""
    if trades.empty or equity.empty:
        return {}
    bars = pd.Series(False, index=equity.index)
    for _, t in trades.iterrows():
        bars.loc[t["entry_time"]:t["exit_time"]] = True
    monthly = trades.set_index("exit_time")["net_pnl"].resample("MS").sum()
    total = monthly.sum()
    best = monthly.max()
    positifs = int((monthly > 0).sum())
    return {
        "temps_en_position": float(bars.mean()),
        "mois_actifs": int((monthly != 0).sum()),
        "mois_positifs": positifs,
        "meilleur_mois_pnl": float(best),
        "part_du_meilleur_mois": float(best / total) if total > 0 else np.nan,
        "pnl_total": float(total),
    }
