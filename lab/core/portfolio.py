"""Portefeuille en compte comptant : cash réglé, cash non réglé, équité en CAD.

Dans un compte comptant, on ne peut acheter qu'avec des fonds **réglés**. Le
produit d'une vente ne l'est qu'après le délai de règlement, ce qui limite
réellement la fréquence des allers-retours avec 200 $.

Le délai a changé : les actions américaines et canadiennes sont passées de
T+2 à T+1 le 27 mai 2024. Un backtest de 10 ans doit donc appliquer les deux
régimes, sans quoi il autorise des trades qui auraient été impossibles.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

T1_EFFECTIVE_DATE = pd.Timestamp("2024-05-27")


def settlement_days(trade_date) -> int:
    """T+2 avant le 27 mai 2024, T+1 à partir de cette date."""
    return 1 if pd.Timestamp(trade_date).normalize() >= T1_EFFECTIVE_DATE else 2


@dataclass
class Portfolio:
    """Cash d'une seule devise (celle de la place) plus l'équité en CAD."""

    cash_settled: float
    usd_per_cad: float
    currency: str = "USD"
    pending: list[tuple[pd.Timestamp, float]] = field(default_factory=list)
    realized_pnl: float = 0.0

    def release_settled(self, today) -> float:
        """Encaisse les produits de vente dont la date de règlement est atteinte."""
        today = pd.Timestamp(today).normalize()
        released = 0.0
        remaining = []
        for settle_date, amount in self.pending:
            if settle_date <= today:
                self.cash_settled += amount
                released += amount
            else:
                remaining.append((settle_date, amount))
        self.pending = remaining
        return released

    @property
    def cash_unsettled(self) -> float:
        return sum(amount for _, amount in self.pending)

    def buying_power(self) -> float:
        """Seul le cash réglé permet d'acheter dans un compte comptant."""
        return self.cash_settled

    def buy(self, notional: float, commission: float) -> None:
        total = notional + commission
        if total > self.cash_settled + 1e-9:
            raise ValueError(
                f"achat de {total:.2f} refusé : seulement {self.cash_settled:.2f} réglé")
        self.cash_settled -= total

    def sell(self, notional: float, commission: float, trade_date,
             sessions: pd.DatetimeIndex | None = None) -> pd.Timestamp:
        """Vend : le produit net devient disponible à la date de règlement."""
        proceeds = notional - commission
        settle = settlement_date(trade_date, sessions)
        self.pending.append((settle, proceeds))
        return settle

    def equity_cad(self, positions_value_local: float = 0.0) -> float:
        total_local = self.cash_settled + self.cash_unsettled + positions_value_local
        return total_local if self.currency == "CAD" else total_local / self.usd_per_cad


def settlement_date(trade_date, sessions: pd.DatetimeIndex | None = None) -> pd.Timestamp:
    """Date de règlement en séances de bourse, pas en jours calendaires."""
    trade_date = pd.Timestamp(trade_date).normalize()
    days = settlement_days(trade_date)
    if sessions is None:
        return trade_date + pd.offsets.BDay(days)
    sessions = pd.DatetimeIndex(sessions).normalize()
    later = sessions[sessions > trade_date]
    if len(later) >= days:
        return later[days - 1]
    return trade_date + pd.offsets.BDay(days)
