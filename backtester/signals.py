"""Composantes de signal et filtres de régime.

Chaque signal S* renvoie un score continu dans [-1, +1] par barre.
Chaque filtre F* renvoie un multiplicateur dans [0, 1].

Causalité : toute valeur à la barre `i` n'utilise que des données jusqu'au close
de `i` inclus. Les quantités calculées sur bougies quotidiennes sont décalées
d'un jour (`shift(1)`) avant d'être ramenées sur l'index horaire, donc pendant
le jour D on ne lit que des journées entièrement closes. Le moteur n'exécute
jamais avant la barre suivante, ce qui laisse une marge supplémentaire.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BARS_PER_DAY = 24
BARS_PER_YEAR = 24 * 365


# --------------------------------------------------------------------------- #
# Briques communes
# --------------------------------------------------------------------------- #
def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff()


def realized_vol(close: pd.Series, window_days: int = 30) -> pd.Series:
    """Volatilité réalisée annualisée à partir des rendements horaires."""
    window = window_days * BARS_PER_DAY
    return log_returns(close).rolling(window, min_periods=window // 2).std() * np.sqrt(BARS_PER_YEAR)


def _daily_to_hourly(daily: pd.Series, hourly_index: pd.DatetimeIndex) -> pd.Series:
    """Décale d'un jour puis réaligne : pendant le jour D on ne voit que <= D-1."""
    shifted = daily.shift(1)
    return shifted.reindex(hourly_index, method="ffill")


def atr(df: pd.DataFrame, period_days: int = 14) -> pd.Series:
    """ATR de Wilder sur bougies quotidiennes, ramené sur l'index horaire."""
    daily = df.resample("1D").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    prev_close = daily["close"].shift(1)
    tr = pd.concat([
        daily["high"] - daily["low"],
        (daily["high"] - prev_close).abs(),
        (daily["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    wilder = tr.ewm(alpha=1 / period_days, adjust=False, min_periods=period_days).mean()
    return _daily_to_hourly(wilder, df.index)


def _rolling_percentile(daily: pd.Series, window_days: int) -> pd.Series:
    """Rang percentile de la valeur courante dans sa fenêtre glissante."""
    return daily.rolling(window_days, min_periods=window_days // 4).apply(
        lambda w: (w[:-1] <= w[-1]).mean(), raw=True
    )


# --------------------------------------------------------------------------- #
# S1 — TSMOM normalisé par la volatilité
# --------------------------------------------------------------------------- #
def s1_tsmom(
    df: pd.DataFrame,
    horizons_days: tuple[int, ...] = (30, 60, 90),
    vol_window_days: int = 30,
    scale: float = 2.0,
) -> pd.Series:
    """Moyenne des rendements sur 30/60/90 j divisés par la vol attendue sur l'horizon."""
    close = df["close"]
    vol_annual = realized_vol(close, vol_window_days)
    scores = []
    for h_days in horizons_days:
        h = h_days * BARS_PER_DAY
        ret = close / close.shift(h) - 1.0
        vol_h = vol_annual * np.sqrt(h_days / 365.0)
        z = ret / vol_h.replace(0.0, np.nan)
        scores.append(np.tanh(z / scale))
    return pd.concat(scores, axis=1).mean(axis=1).clip(-1.0, 1.0)


# --------------------------------------------------------------------------- #
# S2 — Momentum cross-sectional
# --------------------------------------------------------------------------- #
def s2_xsmom(
    close_panel: pd.DataFrame,
    lookback_days: int = 28,
    rebalance_days: int = 7,
) -> pd.DataFrame:
    """Percentile de rang du rendement 28 j entre paires, figé entre rééquilibrages."""
    lookback = lookback_days * BARS_PER_DAY
    ret = close_panel / close_panel.shift(lookback) - 1.0
    ranks = ret.rank(axis=1, pct=True, na_option="keep")
    score = 2.0 * ranks - 1.0
    step = rebalance_days * BARS_PER_DAY
    mask = np.zeros(len(score), dtype=bool)
    mask[::step] = True
    held = score.where(pd.Series(mask, index=score.index), other=np.nan).ffill()
    return held.clip(-1.0, 1.0)


# --------------------------------------------------------------------------- #
# S3 — Donchian breakout
# --------------------------------------------------------------------------- #
def _donchian_state(df: pd.DataFrame, entry_days: int, exit_days: int) -> pd.Series:
    """+1 après cassure du plus haut, -1 après cassure du plus bas, 0 après sortie.

    La sortie dépend de l'état courant (un plus bas de 10 j ne sort que d'un long),
    donc la machine à états est parcourue explicitement — une vectorisation
    confondrait sortie longue et sortie courte.
    """
    entry, exit_ = entry_days * BARS_PER_DAY, exit_days * BARS_PER_DAY
    high_n = df["high"].rolling(entry).max().shift(1).to_numpy()
    low_n = df["low"].rolling(entry).min().shift(1).to_numpy()
    exit_low = df["low"].rolling(exit_).min().shift(1).to_numpy()
    exit_high = df["high"].rolling(exit_).max().shift(1).to_numpy()
    close = df["close"].to_numpy()

    out = np.zeros(len(close))
    state = 0.0
    for i in range(len(close)):
        if state > 0 and not np.isnan(exit_low[i]) and close[i] < exit_low[i]:
            state = 0.0
        elif state < 0 and not np.isnan(exit_high[i]) and close[i] > exit_high[i]:
            state = 0.0
        if state == 0.0:
            if not np.isnan(high_n[i]) and close[i] > high_n[i]:
                state = 1.0
            elif not np.isnan(low_n[i]) and close[i] < low_n[i]:
                state = -1.0
        out[i] = state
    return pd.Series(out, index=df.index)


def s3_donchian(
    df: pd.DataFrame,
    fast: tuple[int, int] = (20, 10),
    slow: tuple[int, int] = (55, 20),
) -> pd.Series:
    """Moyenne des deux systèmes Donchian (20/10 et 55/20)."""
    a = _donchian_state(df, *fast)
    b = _donchian_state(df, *slow)
    return ((a + b) / 2.0).clip(-1.0, 1.0)


# --------------------------------------------------------------------------- #
# S4 — Mean reversion (signal de contrôle)
# --------------------------------------------------------------------------- #
def s4_meanrev(df: pd.DataFrame, ma_days: int = 20, z_cap: float = 2.0) -> pd.Series:
    """Z-score du close vs sa moyenne mobile, borné et inversé."""
    window = ma_days * BARS_PER_DAY
    close = df["close"]
    ma = close.rolling(window, min_periods=window // 2).mean()
    sd = close.rolling(window, min_periods=window // 2).std()
    z = (close - ma) / sd.replace(0.0, np.nan)
    return (-z / z_cap).clip(-1.0, 1.0)


# --------------------------------------------------------------------------- #
# F1 — Kaufman Efficiency Ratio
# --------------------------------------------------------------------------- #
def f1_efficiency_ratio(df: pd.DataFrame, window_bars: int = 20) -> pd.Series:
    close = df["close"]
    direction = (close - close.shift(window_bars)).abs()
    volatility = close.diff().abs().rolling(window_bars).sum()
    er = direction / volatility.replace(0.0, np.nan)
    return er.clip(0.0, 1.0).fillna(0.0)


# --------------------------------------------------------------------------- #
# F2 — Percentile de volatilité réalisée
# --------------------------------------------------------------------------- #
def f2_vol_regime(
    df: pd.DataFrame,
    vol_days: int = 30,
    window_days: int = 365,
    floor: float = 0.2,
) -> pd.Series:
    """Multiplicateur décroissant au-dessus de la médiane de vol : 1.0 -> `floor` au 100e pct."""
    vol = realized_vol(df["close"], vol_days)
    daily_vol = vol.resample("1D").last().dropna()
    pct = _rolling_percentile(daily_vol, window_days)
    mult = 1.0 - (1.0 - floor) * ((pct - 0.5).clip(lower=0.0) / 0.5)
    return _daily_to_hourly(mult, df.index).fillna(1.0).clip(floor, 1.0)


# --------------------------------------------------------------------------- #
# F3 — Funding
# --------------------------------------------------------------------------- #
def f3_funding_regime(
    funding: pd.Series,
    hourly_index: pd.DatetimeIndex,
    window_days: int = 365,
    threshold: float = 0.90,
    penalty: float = 0.3,
) -> pd.Series:
    """Pénalise les longs quand le funding dépasse son 90e percentile glissant."""
    if funding is None or funding.empty:
        return pd.Series(1.0, index=hourly_index)
    per_day = 3  # funding toutes les 8h
    window = window_days * per_day
    pct = funding.rolling(window, min_periods=window // 4).apply(
        lambda w: (w[:-1] <= w[-1]).mean(), raw=True
    )
    mult = pd.Series(np.where(pct > threshold, penalty, 1.0), index=funding.index)
    # Un funding publié à t n'est connu qu'après t : on décale d'un point.
    return mult.shift(1).reindex(hourly_index, method="ffill").fillna(1.0)


# --------------------------------------------------------------------------- #
# Assemblage
# --------------------------------------------------------------------------- #
SIGNAL_FUNCS = {
    "S1_tsmom": s1_tsmom,
    "S3_donchian": s3_donchian,
    "S4_meanrev": s4_meanrev,
}
SIGNAL_NAMES = ["S1_tsmom", "S2_xsmom", "S3_donchian", "S4_meanrev"]
FILTER_NAMES = ["F1_efficiency", "F2_volregime", "F3_funding"]


def build_panels(
    data: dict[str, pd.DataFrame],
    funding: dict[str, pd.Series] | None = None,
    params: dict | None = None,
) -> dict[str, pd.DataFrame]:
    """Construit les matrices (barres × paires) de prix, signaux, filtres et ATR."""
    params = params or {}
    funding = funding or {}
    pairs = sorted(data)
    index = data[pairs[0]].index
    for p in pairs[1:]:
        index = index.union(data[p].index)
    index = index.sort_values()

    per_pair_signals = [n for n in SIGNAL_NAMES if n != "S2_xsmom"]  # S2 est transversal
    frames: dict[str, dict[str, pd.Series]] = {
        k: {} for k in ["open", "high", "low", "close", "atr", "vol", *per_pair_signals, *FILTER_NAMES]
    }
    for pair in pairs:
        df = data[pair].reindex(index)
        for col in ("open", "high", "low", "close"):
            frames[col][pair] = df[col]
        frames["atr"][pair] = atr(df.dropna(subset=["close"]), params.get("atr_days", 14)).reindex(index)
        frames["vol"][pair] = realized_vol(df["close"], params.get("vol_days", 30))
        frames["S1_tsmom"][pair] = s1_tsmom(
            df, params.get("tsmom_horizons", (30, 60, 90)), params.get("vol_days", 30)
        )
        frames["S3_donchian"][pair] = s3_donchian(
            df, params.get("donchian_fast", (20, 10)), params.get("donchian_slow", (55, 20))
        )
        frames["S4_meanrev"][pair] = s4_meanrev(df, params.get("meanrev_days", 20))
        frames["F1_efficiency"][pair] = f1_efficiency_ratio(df, params.get("er_bars", 20))
        frames["F2_volregime"][pair] = f2_vol_regime(
            df, params.get("vol_days", 30), params.get("vol_window_days", 365)
        )
        frames["F3_funding"][pair] = f3_funding_regime(
            funding.get(pair), index, params.get("funding_window_days", 365),
            params.get("funding_threshold", 0.90),
        )

    panels = {k: pd.DataFrame(v, index=index)[pairs] for k, v in frames.items()}
    panels["S2_xsmom"] = s2_xsmom(
        panels["close"], params.get("xsmom_days", 28), params.get("xsmom_rebalance_days", 7)
    )
    return panels
