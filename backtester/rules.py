"""Moteur de règles : indicateurs, pivots, supports, construction du setup.

Toutes les fonctions sont pures et travaillent sur des tableaux numpy, ce qui
permet de les tester sur des données synthétiques sans toucher au réseau.

Invariant de non-look-ahead respecté partout dans ce module :
    une fonction qui reçoit l'indice de barre `i` ne lit jamais un indice > i.
Les pivots portent un `confirm_index` = index + max(right, lag) ; le moteur
n'utilise un pivot que lorsque `confirm_index <= i`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from config import StrategyConfig


@dataclass(frozen=True)
class Pivot:
    index: int
    confirm_index: int
    price: float
    kind: str  # "high" | "low"


@dataclass(frozen=True)
class SupportLevel:
    price: float
    touches: int
    last_index: int


@dataclass(frozen=True)
class Setup:
    """Setup validé au close de `bar_index`, exploitable à partir de bar_index+1."""

    bar_index: int
    l1: float
    l2: float
    stop: float
    b_index: int
    b_price: float
    a_index: int
    a_price: float
    leg: float          # B - A
    ref_entry: float    # entrée théorique (= L1) utilisée pour le pré-filtrage
    ref_target: float
    ref_rr: float


# --------------------------------------------------------------------------- #
# Indicateurs
# --------------------------------------------------------------------------- #
def sma(values: Sequence[float], period: int) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    out = np.full(v.shape, np.nan)
    if len(v) < period:
        return out
    cumsum = np.cumsum(np.insert(v, 0, 0.0))
    out[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return out


def trend_change(close: Sequence[float], lookback: int) -> np.ndarray:
    """Variation relative sur `lookback` barres. NaN tant que l'historique manque."""
    c = np.asarray(close, dtype=float)
    out = np.full(c.shape, np.nan)
    if len(c) > lookback:
        out[lookback:] = c[lookback:] / c[:-lookback] - 1.0
    return out


def trend_filter(close: Sequence[float], cfg: StrategyConfig) -> np.ndarray:
    """Variation sur `trend_lookback` dans [min, max] ET close > SMA(200)."""
    c = np.asarray(close, dtype=float)
    chg = trend_change(c, cfg.trend_lookback)
    ma = sma(c, cfg.sma_period)
    with np.errstate(invalid="ignore"):
        ok = (chg >= cfg.trend_min_change) & (chg <= cfg.trend_max_change) & (c > ma)
    return np.nan_to_num(ok, nan=False).astype(bool)


# --------------------------------------------------------------------------- #
# Pivots
# --------------------------------------------------------------------------- #
def find_pivots(
    high: Sequence[float],
    low: Sequence[float],
    cfg: StrategyConfig,
) -> tuple[list[Pivot], list[Pivot]]:
    """Pivots stricts : le bar central domine strictement ses `left`/`right` voisins.

    Un pivot d'indice i n'est connu qu'une fois les `right` barres suivantes
    clôturées, d'où confirm_index = i + max(right, confirm_lag).
    """
    h = np.asarray(high, dtype=float)
    lo = np.asarray(low, dtype=float)
    n = len(h)
    left, right = cfg.pivot_left, cfg.pivot_right
    lag = max(right, cfg.pivot_confirm_lag)

    highs: list[Pivot] = []
    lows: list[Pivot] = []
    for i in range(left, n - right):
        window_h = h[i - left:i + right + 1]
        if h[i] == window_h.max() and np.count_nonzero(window_h == h[i]) == 1:
            highs.append(Pivot(i, i + lag, float(h[i]), "high"))
        window_l = lo[i - left:i + right + 1]
        if lo[i] == window_l.min() and np.count_nonzero(window_l == lo[i]) == 1:
            lows.append(Pivot(i, i + lag, float(lo[i]), "low"))
    return highs, lows


def confirmed_before(pivots: Iterable[Pivot], bar_index: int) -> list[Pivot]:
    """Pivots utilisables au close de `bar_index` (confirmés, donc sans look-ahead)."""
    return [p for p in pivots if p.confirm_index <= bar_index]


# --------------------------------------------------------------------------- #
# Nouveau sommet B
# --------------------------------------------------------------------------- #
def find_new_high(
    high: Sequence[float],
    bar_index: int,
    cfg: StrategyConfig,
) -> tuple[int, float] | None:
    """Max des `new_high_lookback` dernières barres, s'il date de moins de `max_age`."""
    h = np.asarray(high, dtype=float)
    start = max(0, bar_index - cfg.new_high_lookback + 1)
    window = h[start:bar_index + 1]
    if len(window) < cfg.new_high_lookback:
        return None
    offset = int(np.argmax(window))
    b_index = start + offset
    if bar_index - b_index >= cfg.new_high_max_age:
        return None
    return b_index, float(h[b_index])


# --------------------------------------------------------------------------- #
# Supports : clustering des pivots bas
# --------------------------------------------------------------------------- #
def cluster_lows(pivot_lows: Sequence[Pivot], cfg: StrategyConfig) -> list[SupportLevel]:
    """Regroupe les pivots bas : même cluster tant que l'écart relatif < tolérance.

    Single-linkage sur les prix triés ; le prix du niveau est la moyenne du cluster.
    """
    if not pivot_lows:
        return []
    ordered = sorted(pivot_lows, key=lambda p: p.price)
    clusters: list[list[Pivot]] = [[ordered[0]]]
    for piv in ordered[1:]:
        prev = clusters[-1][-1].price
        if prev > 0 and (piv.price - prev) / prev < cfg.cluster_tolerance:
            clusters[-1].append(piv)
        else:
            clusters.append([piv])
    levels = [
        SupportLevel(
            price=float(np.mean([p.price for p in c])),
            touches=len(c),
            last_index=max(p.index for p in c),
        )
        for c in clusters
    ]
    return sorted(levels, key=lambda lv: lv.price)


def strong_levels(levels: Sequence[SupportLevel], cfg: StrategyConfig) -> list[SupportLevel]:
    return [lv for lv in levels if lv.touches >= cfg.min_touches]


def select_l1_l2(
    levels: Sequence[SupportLevel],
    price: float,
) -> tuple[SupportLevel | None, SupportLevel | None]:
    """L1 = niveau fort le plus proche sous `price`, L2 = le suivant en dessous."""
    below = [lv for lv in levels if lv.price < price]
    if not below:
        return None, None
    below.sort(key=lambda lv: lv.price, reverse=True)
    l1 = below[0]
    l2 = below[1] if len(below) > 1 else None
    return l1, l2


# --------------------------------------------------------------------------- #
# Construction du setup
# --------------------------------------------------------------------------- #
def leg_origin(pivot_lows: Sequence[Pivot], b_index: int, bar_index: int) -> Pivot | None:
    """A = dernier pivot bas confirmé situé avant B (départ de la jambe vers B)."""
    candidates = [p for p in pivot_lows if p.index < b_index and p.confirm_index <= bar_index]
    return max(candidates, key=lambda p: p.index) if candidates else None


def check_entry_levels(
    entry: float,
    stop: float,
    target: float,
    cfg: StrategyConfig,
) -> str | None:
    """Filtres dépendants du prix d'entrée réel. Retourne un motif de skip ou None."""
    if entry <= stop:
        return "entry_below_stop"
    if (entry - stop) / entry > cfg.max_stop_distance:
        return "stop_too_far"
    if target <= entry:
        return "target_below_entry"
    rr = (target - entry) / (entry - stop)
    if rr < cfg.min_rr:
        return "rr_too_low"
    return None


def build_setup(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    bar_index: int,
    pivot_lows: Sequence[Pivot],
    cfg: StrategyConfig,
    trend_ok: bool,
) -> tuple[Setup | None, str]:
    """Évalue le setup au close de `bar_index`. Ne lit aucune donnée après `bar_index`."""
    if not trend_ok:
        return None, "trend_filter"

    nh = find_new_high(high, bar_index, cfg)
    if nh is None:
        return None, "no_new_high"
    b_index, b_price = nh

    window_start = bar_index - cfg.support_lookback + 1
    usable = [
        p for p in pivot_lows
        if p.confirm_index <= bar_index and p.index >= window_start and p.index <= bar_index
    ]
    levels = strong_levels(cluster_lows(usable, cfg), cfg)
    price = float(close[bar_index])
    l1, l2 = select_l1_l2(levels, price)
    if l1 is None:
        return None, "no_l1"
    if l2 is None:
        return None, "no_l2"
    if (l1.price - l2.price) / l1.price > cfg.max_l2_distance:
        return None, "l2_too_far"

    a = leg_origin(pivot_lows, b_index, bar_index)
    if a is None:
        return None, "no_leg_origin"
    leg = b_price - a.price
    if leg <= 0:
        return None, "invalid_leg"

    stop = l2.price * cfg.stop_buffer
    ref_target = l1.price + leg
    reason = check_entry_levels(l1.price, stop, ref_target, cfg)
    if reason is not None:
        return None, reason

    return (
        Setup(
            bar_index=bar_index,
            l1=l1.price,
            l2=l2.price,
            stop=stop,
            b_index=b_index,
            b_price=b_price,
            a_index=a.index,
            a_price=a.price,
            leg=leg,
            ref_entry=l1.price,
            ref_target=ref_target,
            ref_rr=(ref_target - l1.price) / (l1.price - stop),
        ),
        "ok",
    )


def scan_setups(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    cfg: StrategyConfig,
) -> tuple[list[Setup | None], np.ndarray, dict[str, int]]:
    """Setup (ou None) pour chaque barre, plus le masque du filtre de tendance."""
    trend = trend_filter(close, cfg)
    _, pivot_lows = find_pivots(high, low, cfg)
    n = len(close)
    out: list[Setup | None] = [None] * n
    stats: dict[str, int] = {}
    for i in range(n):
        if not trend[i]:
            stats["trend_filter"] = stats.get("trend_filter", 0) + 1
            continue
        setup, reason = build_setup(high, low, close, i, pivot_lows, cfg, True)
        stats[reason] = stats.get(reason, 0) + 1
        out[i] = setup
    return out, trend, stats
