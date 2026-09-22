"""Momentum mensuel : rotation parmi un panier de FNBs."""

from __future__ import annotations

import pandas as pd

from .base import ExitRule, OrderType, Signal, Strategy, Context


class MomentumMonthly(Strategy):
    """
    Rotation mensuelle : sélectionner le FNB au meilleur rendement 6M ou 12M,
    ou rester en cash (BIL/SGOV) si cash dépasse tous les FNBs.
    Une seule position à la fois. Stop/risque: max drawdown historique.
    """

    def __init__(self, universe: list[str] | None = None,
                 lookback_months: int = 6, cash_symbol: str = "BIL"):
        """
        Args:
            universe: liste des symboles à comparer (ex: ['SPY', 'TLT', 'GLD'])
            lookback_months: 6 ou 12 pour le calcul de momentum
            cash_symbol: symbole de l'actif "cash" (par défaut BIL)
        """
        self.universe = universe or ["SPY", "TLT", "GLD", "EFA"]
        self.lookback_months = lookback_months
        self.cash_symbol = cash_symbol
        self.lookback_bars = lookback_months * 21  # environ 21 jours de bourse par mois

    @property
    def timeframe(self) -> str:
        return "1d"

    def universe_filter(self, symbol: str, data: pd.DataFrame) -> bool:
        """Vérifier que le symbole est dans l'univers et a suffisant d'historique."""
        if symbol not in self.universe and symbol != self.cash_symbol:
            return False
        return len(data) >= self.lookback_bars

    def on_bar_close(self, ctx: Context) -> Signal | None:
        """
        À chaque fin de mois, retourner le signal du momentum gagnant.
        Le contexte doit être appelé une fois par jour pour chaque symbole de l'univers.
        """
        h = ctx.history
        if len(h) < self.lookback_bars:
            return None

        # Vérifier si c'est une fin de mois (nombre de jours depuis fin du mois < 5)
        today = h.index[-1]
        if not self._is_month_end(today):
            return None

        # Calculer le rendement 6M/12M pour chaque symbole
        close = h["close"]
        return_values = close.iloc[-1] / close.iloc[-self.lookback_bars] - 1

        # Meilleur choix : le plus haut rendement
        # (normalement on devrait regarder les rendements de *tous* les symboles,
        # mais ce contexte n'a que l'historique du symbole courant)
        # Pour Phase C, on implémente une version simplifiée :
        # on signal seulement si le symbole courant a un bon momentum
        momentum_pct = return_values * 100

        if momentum_pct > 0:  # rendement positif
            return Signal(
                symbol=ctx.symbol,
                order_type=OrderType.MARKET,
                limit_price=None,
                stop=0,  # pas de stop au sens classique du risque
                exit_rule=ExitRule.SIGNAL,
                exit_param=None,
                expiration_bars=30,  # réévaluer à la fin du mois prochain
                reason=f"Momentum monthly: {ctx.symbol} rendement 6M = {momentum_pct:.1f}%. "
                       f"Sortie à la fin du mois ou sur signal nouveau."
            )
        else:
            # Rendement négatif : passer à cash
            return Signal(
                symbol=self.cash_symbol,
                order_type=OrderType.MARKET,
                limit_price=None,
                stop=0,
                exit_rule=ExitRule.SIGNAL,
                exit_param=None,
                expiration_bars=30,
                reason=f"Momentum monthly: {ctx.symbol} rendement 6M = {momentum_pct:.1f}%. "
                       f"Passer à {self.cash_symbol}."
            )

    def _is_month_end(self, date: pd.Timestamp) -> bool:
        """Détecter si la date est proche de la fin du mois."""
        # Dernier jour du mois ou dans les 5 jours avant
        days_left = (pd.Timestamp(date) + pd.offsets.MonthEnd() - pd.Timestamp(date)).days
        return days_left <= 5

    def params_grid(self) -> list[dict]:
        """Grille de sensibilité : universes et lookback."""
        return [
            {"universe": ["SPY", "TLT", "GLD", "EFA"], "lookback_months": 6,
             "cash_symbol": "BIL"},
            {"universe": ["SPY", "TLT", "GLD", "EFA"], "lookback_months": 12,
             "cash_symbol": "BIL"},
            {"universe": ["SPY", "IWM", "EFA"], "lookback_months": 6,
             "cash_symbol": "BIL"},
            {"universe": ["QQQ", "TLT", "GLD"], "lookback_months": 6,
             "cash_symbol": "BIL"},
            {"universe": ["SPY", "QQQ", "IWM", "TLT", "GLD", "EFA"], "lookback_months": 6,
             "cash_symbol": "SGOV"},
        ]
