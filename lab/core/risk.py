"""Dimensionnement et garde-fous de risque.

Le plafond de 5 $ CAD est **frais aller-retour inclus** : c'est le moteur qui
l'impose, jamais la stratégie. Une position dont la perte au stop dépasserait
ce plafond, commissions comprises, est refusée ou réduite.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import costs

RISK_TARGET_CAD = 3.0        # fourchette 2 à 4 $ du brief
MAX_RISK_CAD = 5.0           # plafond absolu, frais aller-retour inclus
MAX_CONSECUTIVE_LOSSES = 2   # pause après 2 pertes d'affilée
MAX_OPEN_POSITIONS = 1


@dataclass(frozen=True)
class Sizing:
    shares: float
    risk_cad: float          # perte au stop, commissions comprises
    notional_local: float
    commission_round_trip_local: float
    rejected: str | None = None

    @property
    def ok(self) -> bool:
        return self.rejected is None and self.shares > 0


def size_position(
    entry: float,
    stop: float,
    symbol: str,
    cash_local: float,
    usd_per_cad: float,
    plan: str = "tiered",
    risk_target_cad: float = RISK_TARGET_CAD,
    max_risk_cad: float = MAX_RISK_CAD,
    fractional: bool = False,
) -> Sizing:
    """Plus grande position dont la perte au stop reste sous le plafond.

    Les commissions sont incluses dans le risque, ce qui change tout à cette
    taille de compte : sur un ordre de 100 $, le minimum Fixed de 1 $ pèse
    autant que 1 % de mouvement de prix.
    """
    currency = costs.GRIDS[(costs.venue_of(symbol), plan)].currency
    if entry <= 0 or stop <= 0 or entry <= stop:
        return Sizing(0, 0, 0, 0, "stop au-dessus ou égal à l'entrée")

    per_share_loss_cad = costs.to_cad(entry - stop, currency, usd_per_cad)
    if per_share_loss_cad <= 0:
        return Sizing(0, 0, 0, 0, "distance au stop nulle")

    # Point de départ : la cible de risque sans les frais, puis on décrémente
    # jusqu'à ce que le risque commissions comprises tienne sous le plafond.
    shares = risk_target_cad / per_share_loss_cad
    if not fractional:
        shares = float(int(shares))

    step = 0.1 if fractional else 1.0
    while shares > 0:
        notional = shares * entry
        if notional > cash_local:
            shares -= step
            shares = round(shares, 4)
            continue
        fees_local = costs.round_trip_cost(shares, entry, stop, symbol, plan, fractional)
        risk_cad = (shares * per_share_loss_cad
                    + costs.to_cad(fees_local, currency, usd_per_cad))
        if risk_cad <= max_risk_cad:
            return Sizing(shares, risk_cad, notional, fees_local)
        shares -= step
        shares = round(shares, 4)

    # Même une action (ou la plus petite fraction) dépasse le plafond.
    smallest = step
    notional = smallest * entry
    fees_local = costs.round_trip_cost(smallest, entry, stop, symbol, plan, fractional)
    risk_cad = smallest * per_share_loss_cad + costs.to_cad(fees_local, currency, usd_per_cad)
    reason = ("capital insuffisant pour une action" if notional > cash_local
              else f"risque minimal {risk_cad:.2f} $ > plafond {max_risk_cad:.2f} $")
    return Sizing(0, risk_cad, notional, fees_local, reason)


@dataclass
class RiskState:
    """Suit les pertes consécutives et l'unique position ouverte."""

    consecutive_losses: int = 0
    open_positions: int = 0
    paused: bool = False

    def can_open(self, max_open: int = MAX_OPEN_POSITIONS) -> tuple[bool, str]:
        if self.paused:
            return False, f"pause après {self.consecutive_losses} pertes consécutives"
        if self.open_positions >= max_open:
            return False, "une seule position à la fois"
        return True, ""

    def on_open(self) -> None:
        self.open_positions += 1

    def on_close(self, pnl_cad: float,
                 max_consecutive: int = MAX_CONSECUTIVE_LOSSES) -> None:
        self.open_positions = max(0, self.open_positions - 1)
        if pnl_cad < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= max_consecutive:
                self.paused = True
        else:
            self.consecutive_losses = 0

    def resume(self) -> None:
        """Reprise après la pause — décision explicite, jamais automatique."""
        self.paused = False
        self.consecutive_losses = 0
