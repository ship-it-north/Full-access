"""Swing pullback : tendance, repli vers EMA 20, puis reprise."""

from __future__ import annotations

import pandas as pd

from .base import ExitRule, OrderType, Signal, Strategy, Context


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


class SwingPullback(Strategy):
    """
    Tendance haussière + repli vers EMA 20 + reprise (clôture au-dessus du HH de veille).
    Entrée à l'ouverture suivante, stop sous le creux du repli moins 0,5x ATR.
    Sortie : 2R, stop suiveur ATR, ou après 10 jours.
    """

    def __init__(self, sma50_period: int = 50, sma200_period: int = 200,
                 ema20_period: int = 20, atr_period: int = 14,
                 atr_stop_factor: float = 0.5, target_r: float = 2.0,
                 trailing_atr_factor: float = 1.5, max_days: int = 10):
        self.sma50_period = sma50_period
        self.sma200_period = sma200_period
        self.ema20_period = ema20_period
        self.atr_period = atr_period
        self.atr_stop_factor = atr_stop_factor
        self.target_r = target_r
        self.trailing_atr_factor = trailing_atr_factor
        self.max_days = max_days

    @property
    def timeframe(self) -> str:
        return "1d"

    def universe_filter(self, symbol: str, data: pd.DataFrame) -> bool:
        """Universes avec suffisant d'historique et liquidité acceptable."""
        if len(data) < 200:
            return False
        # Volume moyen sur 30 jours > 100k ou prix > 10
        avg_vol = data["volume"].tail(30).mean()
        price = data["close"].iloc[-1]
        return avg_vol > 100_000 or price > 10

    def on_bar_close(self, ctx: Context) -> Signal | None:
        """
        Conditions de tendance + repli + reprise détectées -> signal.
        """
        h = ctx.history
        if len(h) < self.sma200_period + 5:
            return None

        close = h["close"]
        high = h["high"]
        low = h["low"]

        # Indicateurs
        sma50 = close.rolling(self.sma50_period).mean()
        sma200 = close.rolling(self.sma200_period).mean()
        ema20 = close.ewm(span=self.ema20_period, adjust=False).mean()
        atr_vals = atr(high, low, close, self.atr_period)

        # Tendance : close > SMA50 > SMA200
        trend_ok = (close.iloc[-1] > sma50.iloc[-1] and
                    sma50.iloc[-1] > sma200.iloc[-1])
        if not trend_ok:
            return None

        # Repli + reprise : bas récent < EMA20, puis close > max(high[-2:])
        recent_low = low.iloc[-20:].min()
        pullback_ok = recent_low < ema20.iloc[-1]
        recovery_ok = close.iloc[-1] > high.iloc[-2]

        if not (pullback_ok and recovery_ok):
            return None

        # Stop : sous le creux du repli moins 0.5x ATR
        stop_price = recent_low - self.atr_stop_factor * atr_vals.iloc[-1]

        return Signal(
            symbol=ctx.symbol,
            order_type=OrderType.MARKET,
            limit_price=None,
            stop=stop_price,
            exit_rule=ExitRule.TARGET,
            exit_param=self.target_r,
            expiration_bars=self.max_days,
            reason=f"Swing pullback: tendance + repli vers EMA20 + reprise. "
                   f"Stop à {stop_price:.2f}, cible 2R."
        )

    def params_grid(self) -> list[dict]:
        """Grille de sensibilité ~ 20 combinaisons."""
        return [
            {"sma50_period": 50, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 50, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 1.0, "target_r": 2.0},
            {"sma50_period": 50, "sma200_period": 200, "ema20_period": 15,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 40, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 60, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 50, "sma200_period": 180, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 50, "sma200_period": 220, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 2.0},
            {"sma50_period": 50, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 1.5},
            {"sma50_period": 50, "sma200_period": 200, "ema20_period": 20,
             "atr_stop_factor": 0.5, "target_r": 3.0},
        ]
