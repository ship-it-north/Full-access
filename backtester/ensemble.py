"""Moteur de portefeuille pour l'ensemble de signaux.

Sert aussi bien à backtester une composante isolée (phase 1) que l'ensemble
complet (phase 2) : une composante seule est un ensemble à un signal, sans filtre.

Causalité : à la barre `i`, la décision utilise exclusivement la ligne `i-1`
(scores, ATR, vol, corrélations) et l'exécution se fait à l'ouverture de `i`.
Les stops sont évalués sur le range de la barre `i` ; un stop suiveur recalculé
au close de `i` ne s'applique qu'à partir de `i+1`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

import config as C

BARS_PER_DAY = 24
DAYS_PER_YEAR = 365

# Compteur global : toute configuration évaluée est comptée (Deflated Sharpe Ratio).
RUN_COUNTER = {"n": 0}


@dataclass(frozen=True)
class EnsembleConfig:
    weights: tuple[tuple[str, float], ...] = (("S1_tsmom", 1.0),)
    filters: tuple[str, ...] = ()
    threshold: float = 0.3
    atr_stop_mult: float = 2.5
    atr_trail_mult: float = 3.0
    trail_after_r: float = 1.0
    sizing: str = "voltarget"        # "voltarget" | "fixed"
    vol_target: float = 0.20
    max_risk: float = 0.05
    fixed_risk: float = 0.02
    max_positions: int = 5
    max_corr: float = 0.7
    max_gross: float = 2.0
    initial_capital: float = 100.0
    cost_mult: float = 1.0
    label: str = ""

    @property
    def weight_map(self) -> dict[str, float]:
        return dict(self.weights)


@dataclass
class EnsembleResult:
    config: EnsembleConfig
    trades: pd.DataFrame
    equity: pd.Series
    daily_returns: pd.Series
    ruined: bool = False


def composite_score(panels: dict[str, pd.DataFrame], cfg: EnsembleConfig) -> pd.DataFrame:
    """Moyenne pondérée des signaux retenus × produit des filtres de régime."""
    weights = cfg.weight_map
    total = sum(abs(w) for w in weights.values()) or 1.0
    score = sum(panels[name] * w for name, w in weights.items()) / total
    for name in cfg.filters:
        score = score * panels[name]
    return score.clip(-1.0, 1.0)


def rolling_correlations(close: pd.DataFrame, window_days: int = 30) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """Matrices de corrélation 30 j des rendements quotidiens, une par journée."""
    daily = close.resample("1D").last()
    rets = np.log(daily).diff()
    values = rets.to_numpy()
    n_days, n_pairs = values.shape
    out = np.full((n_days, n_pairs, n_pairs), np.nan)
    for d in range(window_days, n_days):
        window = values[d - window_days + 1:d + 1]
        valid = ~np.isnan(window).any(axis=0)
        if valid.sum() < 2:
            continue
        sub = window[:, valid]
        corr = np.corrcoef(sub, rowvar=False)
        idx = np.where(valid)[0]
        out[d][np.ix_(idx, idx)] = corr
    return out, daily.index


def run_ensemble(
    panels: dict[str, pd.DataFrame],
    cfg: EnsembleConfig,
    corr_cube: tuple[np.ndarray, pd.DatetimeIndex] | None = None,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> EnsembleResult:
    RUN_COUNTER["n"] += 1

    score = composite_score(panels, cfg)
    index = panels["close"].index
    mask = np.ones(len(index), dtype=bool)
    if start is not None:
        mask &= index >= start
    if end is not None:
        mask &= index <= end
    window_index = index[mask]
    if len(window_index) < 2:
        empty = pd.Series(dtype=float)
        return EnsembleResult(cfg, pd.DataFrame(), empty, empty)

    pairs = list(panels["close"].columns)
    o = panels["open"].to_numpy(float)
    h = panels["high"].to_numpy(float)
    lo = panels["low"].to_numpy(float)
    c = panels["close"].to_numpy(float)
    a = panels["atr"].to_numpy(float)
    v = panels["vol"].to_numpy(float)
    s = score.to_numpy(float)
    # Univers point-in-time : une paire hors du top 30 du mois ne peut pas être
    # ouverte, mais une position déjà ouverte reste gérée jusqu'à sa sortie.
    member = (
        panels["membership"].to_numpy(bool)
        if "membership" in panels
        else np.ones_like(s, dtype=bool)
    )

    corr_values, corr_index = corr_cube if corr_cube is not None else rolling_correlations(panels["close"])
    corr_pos = corr_index.searchsorted(index, side="right") - 1

    fee = C.TAKER_FEE * cfg.cost_mult
    slip = C.STOP_SLIPPAGE * cfg.cost_mult
    funding_per_bar = C.FUNDING_RATE_8H / C.FUNDING_INTERVAL_BARS

    equity = cfg.initial_capital
    positions: dict[int, dict] = {}
    trades: list[dict] = []
    curve = np.empty(len(window_index))
    ruined = False

    offsets = np.where(mask)[0]
    for step, i in enumerate(offsets):
        if i == 0:
            curve[step] = equity
            continue
        prev = i - 1

        # --- 1. Gestion des positions ouvertes (range de la barre i) -------- #
        for j in list(positions):
            pos = positions[j]
            if np.isnan(c[i, j]):
                continue
            exit_price = exit_reason = None
            if lo[i, j] <= pos["stop"]:
                base = min(pos["stop"], o[i, j]) if o[i, j] < pos["stop"] else pos["stop"]
                exit_price, exit_reason = base * (1 - slip), "stop"
            elif s[prev, j] < 0:
                exit_price, exit_reason = o[i, j], "score_exit"

            if exit_price is not None:
                equity = _close(trades, pos, pairs[j], index[i], i, exit_price, exit_reason,
                                equity, fee, funding_per_bar)
                del positions[j]
                if equity <= 0:
                    ruined = True
                    break
                continue

            pos["max_high"] = max(pos["max_high"], h[i, j])
            r_unit = pos["entry"] - pos["initial_stop"]
            if pos["max_high"] >= pos["entry"] + cfg.trail_after_r * r_unit and not np.isnan(a[i, j]):
                # Stop suiveur armé au close : effectif à partir de la barre suivante.
                pos["stop"] = max(pos["stop"], pos["max_high"] - cfg.atr_trail_mult * a[i, j])

        if ruined:
            curve[step:] = max(equity, 0.0)
            break

        # --- 2. Candidats à l'entrée (décision sur la ligne i-1) ------------ #
        if len(positions) < cfg.max_positions:
            gross = sum(p["qty"] * c[prev, j] for j, p in positions.items() if not np.isnan(c[prev, j]))
            row = s[prev]
            candidates = np.where(
                (row > cfg.threshold)
                & member[prev]
                & ~np.isnan(o[i])
                & ~np.isnan(a[prev])
                & (a[prev] > 0)
            )[0]
            d = corr_pos[prev]
            for j in sorted(candidates, key=lambda x: -row[x]):
                if len(positions) >= cfg.max_positions or j in positions:
                    continue
                if not _corr_ok(corr_values, d, j, positions, cfg.max_corr):
                    continue
                entry = o[i, j]
                stop = entry - cfg.atr_stop_mult * a[prev, j]
                if stop <= 0 or entry <= stop:
                    continue
                risk_pct = _risk_pct(v[prev, j], cfg)
                if risk_pct is None:
                    continue
                qty = risk_pct * equity / (entry - stop)
                notional = qty * entry
                capacity = cfg.max_gross * equity - gross
                if capacity <= 0.1 * equity:
                    break
                if notional > capacity:
                    qty *= capacity / notional
                    notional = capacity
                if qty <= 0:
                    continue
                gross += notional
                positions[j] = {
                    "entry": entry, "entry_index": i, "entry_time": index[i],
                    "stop": stop, "initial_stop": stop, "qty": qty,
                    "risk": qty * (entry - stop), "notional": notional,
                    "max_high": h[i, j], "score": row[j], "risk_pct": risk_pct,
                }

        unrealized = sum(
            p["qty"] * (c[i, j] - p["entry"]) for j, p in positions.items() if not np.isnan(c[i, j])
        )
        curve[step] = equity + unrealized

    equity_series = pd.Series(curve, index=window_index)
    trades_df = pd.DataFrame(trades)
    daily = equity_series.resample("1D").last().dropna()
    daily_returns = daily.pct_change().dropna()
    return EnsembleResult(cfg, trades_df, equity_series, daily_returns, ruined)


def _risk_pct(vol: float, cfg: EnsembleConfig) -> float | None:
    if cfg.sizing == "fixed":
        return cfg.fixed_risk
    if np.isnan(vol) or vol <= 0:
        return None
    return float(min(cfg.vol_target / vol, cfg.max_risk))


def _corr_ok(corr_values: np.ndarray, d: int, j: int, positions: dict, max_corr: float) -> bool:
    if d < 0 or d >= len(corr_values) or not positions:
        return True
    for k in positions:
        rho = corr_values[d, j, k]
        if not np.isnan(rho) and rho >= max_corr:
            return False
    return True


def _close(trades, pos, pair, ts, i, exit_price, reason, equity, fee, funding_per_bar) -> float:
    bars = i - pos["entry_index"]
    gross = pos["qty"] * (exit_price - pos["entry"])
    fees = pos["notional"] * fee + pos["qty"] * exit_price * fee
    funding = pos["notional"] * funding_per_bar * bars
    net = gross - fees - funding
    equity += net
    trades.append({
        "pair": pair,
        "entry_time": pos["entry_time"],
        "exit_time": ts,
        "entry_price": pos["entry"],
        "initial_stop": pos["initial_stop"],
        "exit_price": exit_price,
        "exit_reason": reason,
        "bars_held": bars,
        "qty": pos["qty"],
        "notional": pos["notional"],
        "risk_amount": pos["risk"],
        "risk_pct": pos["risk_pct"],
        "entry_score": pos["score"],
        "gross_pnl": gross,
        "fees": fees,
        "funding": funding,
        "net_pnl": net,
        "r_multiple": net / pos["risk"] if pos["risk"] else 0.0,
        "equity_after": equity,
    })
    return equity


# --------------------------------------------------------------------------- #
# Métriques
# --------------------------------------------------------------------------- #
def sharpe(daily_returns: pd.Series) -> float:
    if len(daily_returns) < 10 or daily_returns.std() < 1e-12:
        return float("nan")
    return float(daily_returns.mean() / daily_returns.std() * np.sqrt(DAYS_PER_YEAR))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def metrics(result: EnsembleResult, label: str = "") -> dict:
    t, eq = result.trades, result.equity
    out = {
        "strategie": label or result.config.label,
        "trades": int(len(t)),
        "sharpe": sharpe(result.daily_returns),
        "rendement_total": float(eq.iloc[-1] / eq.iloc[0] - 1.0) if len(eq) else 0.0,
        "max_drawdown": max_drawdown(eq),
    }
    if t.empty:
        out.update({"win_rate": np.nan, "esperance_R": np.nan, "profit_factor": np.nan,
                    "R_total": 0.0, "duree_moyenne_h": np.nan})
        return out
    wins, losses = t[t.net_pnl > 0], t[t.net_pnl <= 0]
    loss_sum = abs(losses.net_pnl.sum())
    out.update({
        "win_rate": float(len(wins) / len(t)),
        "esperance_R": float(t.r_multiple.mean()),
        "profit_factor": float(wins.net_pnl.sum() / loss_sum) if loss_sum > 0 else np.inf,
        "R_total": float(t.r_multiple.sum()),
        "duree_moyenne_h": float(t.bars_held.mean()),
    })
    return out
