"""Exécution simulée.

Règles imposées par le brief, appliquées par le moteur et non par la stratégie :
  - stratégies quotidiennes : signal au close, entrée à l'ouverture suivante
    avec glissement ;
  - stop et cible touchés dans la même barre : on suppose le stop touché en
    premier (hypothèse conservatrice) ;
  - ouverture sous le stop : la sortie se fait à l'ouverture, pas au stop.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

DEFAULT_SLIPPAGE_BPS = 5.0   # 0,05 % sur les ordres au marché


@dataclass(frozen=True)
class Fill:
    price: float
    reason: str


def apply_slippage(price: float, side: str, slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> float:
    """Le glissement joue toujours contre nous."""
    factor = 1 + slippage_bps / 10_000 * (1 if side == "buy" else -1)
    return price * factor


def entry_fill(next_bar: pd.Series, side: str = "buy",
               slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
               limit: float | None = None) -> Fill | None:
    """Entrée à l'ouverture de la barre suivante, ou sur limite atteinte."""
    if next_bar is None or pd.isna(next_bar.get("open")):
        return None
    if limit is None:
        return Fill(apply_slippage(float(next_bar["open"]), side, slippage_bps), "open")
    if side == "buy":
        if float(next_bar["open"]) <= limit:
            return Fill(float(next_bar["open"]), "limite (ouverture sous la limite)")
        if float(next_bar["low"]) <= limit:
            return Fill(limit, "limite")
        return None
    if float(next_bar["open"]) >= limit:
        return Fill(float(next_bar["open"]), "limite (ouverture au-dessus)")
    if float(next_bar["high"]) >= limit:
        return Fill(limit, "limite")
    return None


def exit_fill(bar: pd.Series, stop: float, target: float | None,
              slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> Fill | None:
    """Sortie sur une barre : stop prioritaire, gap exécuté à l'ouverture."""
    o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])

    # Ouverture déjà sous le stop : on sort à l'ouverture, pas au stop.
    if o <= stop:
        return Fill(apply_slippage(o, "sell", slippage_bps), "gap sous le stop")
    if target is not None and o >= target:
        return Fill(o, "gap au-dessus de la cible")

    touche_stop = l <= stop
    touche_cible = target is not None and h >= target
    if touche_stop and touche_cible:
        # Chemin intra-barre inconnu : hypothèse conservatrice.
        return Fill(apply_slippage(stop, "sell", slippage_bps), "stop et cible même barre")
    if touche_stop:
        return Fill(apply_slippage(stop, "sell", slippage_bps), "stop")
    if touche_cible:
        return Fill(target, "cible")
    return None


def time_exit_fill(bar: pd.Series, slippage_bps: float = DEFAULT_SLIPPAGE_BPS) -> Fill:
    """Sortie temporelle : au marché, à la clôture de la barre."""
    return Fill(apply_slippage(float(bar["close"]), "sell", slippage_bps), "sortie temporelle")
