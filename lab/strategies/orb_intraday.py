"""ORB intraday : casse de plage d'ouverture avec contrainte de disponibilité."""

from __future__ import annotations

import pandas as pd

from .base import ExitRule, OrderType, Signal, Strategy, Context


class ORBIntraday(Strategy):
    """
    Opening Range Breakout (5 min) : range sur les premières N barres,
    puis entrée au casse de la plage. Tight stops et cibles.
    Limité aux heures où Philippe peut approuver (pénalité).
    """

    def __init__(self, range_bars: int = 6, breakout_pct: float = 0.05,
                 target_r: float = 1.5, approval_start_hour: int = 16,
                 approval_end_hour: int = 23, approval_start_next_hour: int = 9,
                 approval_end_next_hour: int = 30):
        """
        Args:
            range_bars: nombre de barres pour construire la plage (ex: 6 pour 30 min)
            breakout_pct: % de casse du range pour déclencher
            target_r: rapport risque/gain cible
            approval_*: heures de disponibilité de Philippe (NY time)
                Si entre 9:30 et 16:00 en semaine: interdire l'ORB
        """
        self.range_bars = range_bars
        self.breakout_pct = breakout_pct
        self.target_r = target_r
        self.approval_start_hour = approval_start_hour
        self.approval_end_hour = approval_end_hour
        self.approval_start_next_hour = approval_start_next_hour
        self.approval_end_next_hour = approval_end_next_hour

    @property
    def timeframe(self) -> str:
        return "5m"

    def universe_filter(self, symbol: str, data: pd.DataFrame) -> bool:
        """ORB sur actions / ETF liquides à l'ouverture."""
        if len(data) < 100:
            return False
        # Vérifier que les 5 premiers jours ont des barres de 5 min
        # (au moins 75 barres = 6.25 heures)
        if len(data) < 75:
            return False
        avg_vol = data["volume"].tail(20).mean()
        price = data["close"].iloc[-1]
        return avg_vol > 50_000 or price > 5  # plus souple qu'en daily

    def _is_approval_allowed(self, timestamp: pd.Timestamp) -> bool:
        """
        Vérifier si Philippe peut approuver un signal maintenant.
        Par défaut : 9:30-16:00 ET semaine = signal bloqué.
        """
        ny_time = timestamp.tz_localize("UTC").tz_convert("America/New_York")
        hour = ny_time.hour
        minute = ny_time.minute
        weekday = ny_time.weekday()  # 0=lundi, 4=vendredi, 5-6=week-end

        # Week-end : pas de restriction
        if weekday >= 5:
            return True

        # Horaires interdits : 9:30-16:00 (9h30 à 4pm)
        if hour >= 9 and (hour < 16 or (hour == 16 and minute == 0)):
            if hour == 9 and minute < 30:
                # Avant 9:30 le matin : OK
                return True
            # 9:30-16:00 : bloqué
            return False

        # Autres horaires : OK
        return True

    def on_bar_close(self, ctx: Context) -> Signal | None:
        """
        Construire la plage du range, détecter le casse.
        """
        h = ctx.history
        if len(h) < self.range_bars + 5:
            return None

        # Vérifier si l'approbation est possible maintenant
        if not self._is_approval_allowed(h.index[-1]):
            return None

        close = h["close"]
        high = h["high"]
        low = h["low"]

        # Construire la plage sur les premières barres de la journée
        # (supposer que les N premières barres = premières 30 min)
        range_high = high.iloc[-self.range_bars:].max()
        range_low = low.iloc[-self.range_bars:].min()
        range_width = range_high - range_low

        if range_width <= 0:
            return None

        # Breakout : casse de X% au-dessus/au-dessous du range
        breakout_threshold_up = range_high + range_width * self.breakout_pct
        breakout_threshold_down = range_low - range_width * self.breakout_pct

        current_close = close.iloc[-1]
        current_high = high.iloc[-1]
        current_low = low.iloc[-1]

        # Détection de casse
        if current_high > breakout_threshold_up:
            # Casse à la hausse
            stop = range_low
            risk = current_close - stop
            if risk <= 0:
                return None
            target = current_close + risk * self.target_r

            return Signal(
                symbol=ctx.symbol,
                order_type=OrderType.MARKET,
                limit_price=None,
                stop=stop,
                exit_rule=ExitRule.TARGET,
                exit_param=self.target_r,
                expiration_bars=4,  # expiration le même jour
                reason=f"ORB long: range {range_low:.2f}-{range_high:.2f}, "
                       f"casse >{ breakout_threshold_up:.2f}. "
                       f"Stop {stop:.2f}, cible {target:.2f}."
            )
        elif current_low < breakout_threshold_down:
            # Casse à la baisse
            stop = range_high
            risk = stop - current_close
            if risk <= 0:
                return None
            target = current_close - risk * self.target_r

            return Signal(
                symbol=ctx.symbol,
                order_type=OrderType.MARKET,
                limit_price=None,
                stop=stop,
                exit_rule=ExitRule.TARGET,
                exit_param=self.target_r,
                expiration_bars=4,
                reason=f"ORB short: range {range_low:.2f}-{range_high:.2f}, "
                       f"casse <{breakout_threshold_down:.2f}. "
                       f"Stop {stop:.2f}, cible {target:.2f}."
            )

        return None

    def params_grid(self) -> list[dict]:
        """Grille de sensibilité : range duration et breakout %."""
        return [
            {"range_bars": 6, "breakout_pct": 0.05, "target_r": 1.5},
            {"range_bars": 6, "breakout_pct": 0.10, "target_r": 1.5},
            {"range_bars": 4, "breakout_pct": 0.05, "target_r": 1.5},
            {"range_bars": 8, "breakout_pct": 0.05, "target_r": 1.5},
            {"range_bars": 6, "breakout_pct": 0.05, "target_r": 1.0},
            {"range_bars": 6, "breakout_pct": 0.05, "target_r": 2.0},
        ]
