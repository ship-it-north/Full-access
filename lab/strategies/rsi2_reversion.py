"""RSI(2) mean reversion : extremes bas, sortie rapide."""

from __future__ import annotations

import pandas as pd

from .base import ExitRule, OrderType, Signal, Strategy, Context


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


class RSI2Reversion(Strategy):
    """
    RSI(2) sous seuil bas (comme 10) dans tendance haussière (> SMA200).
    Entrée au marché à l'ouverture suivante.
    Sortie : clôture > SMA5, ou après 5 jours, ou stop 2.5x ATR (plafond 5 $).
    """

    def __init__(self, sma200_period: int = 200, sma5_period: int = 5,
                 rsi2_threshold: float = 10.0, atr_period: int = 14,
                 stop_atr_factor: float = 2.5, max_days: int = 5):
        self.sma200_period = sma200_period
        self.sma5_period = sma5_period
        self.rsi2_threshold = rsi2_threshold
        self.atr_period = atr_period
        self.stop_atr_factor = stop_atr_factor
        self.max_days = max_days

    @property
    def timeframe(self) -> str:
        return "1d"

    def universe_filter(self, symbol: str, data: pd.DataFrame) -> bool:
        """Suffisant d'historique et liquidité acceptable."""
        if len(data) < 200:
            return False
        avg_vol = data["volume"].tail(30).mean()
        price = data["close"].iloc[-1]
        return avg_vol > 100_000 or price > 10

    def on_bar_close(self, ctx: Context) -> Signal | None:
        """
        RSI(2) < seuil + tendance haussière -> signal.
        """
        h = ctx.history
        if len(h) < self.sma200_period + 5:
            return None

        close = h["close"]
        high = h["high"]
        low = h["low"]

        # Indicateurs
        sma200 = close.rolling(self.sma200_period).mean()
        sma5 = close.rolling(self.sma5_period).mean()
        rsi2_vals = rsi(close, period=2)
        atr_vals = atr(high, low, close, self.atr_period)

        # Tendance : close > SMA200
        trend_ok = close.iloc[-1] > sma200.iloc[-1]
        if not trend_ok:
            return None

        # RSI(2) très bas
        rsi2_extreme = rsi2_vals.iloc[-1] < self.rsi2_threshold
        if not rsi2_extreme:
            return None

        # Stop : 2.5x ATR au-dessus du cours actuel (pour plafond 5 $)
        stop_price = close.iloc[-1] - self.stop_atr_factor * atr_vals.iloc[-1]

        return Signal(
            symbol=ctx.symbol,
            order_type=OrderType.MARKET,
            limit_price=None,
            stop=stop_price,
            exit_rule=ExitRule.SIGNAL,
            exit_param=None,
            expiration_bars=self.max_days,
            reason=f"RSI(2) reversion: RSI={rsi2_vals.iloc[-1]:.1f} < {self.rsi2_threshold}. "
                   f"Stop à {stop_price:.2f}, sortie sur clôture > SMA5 ou après {self.max_days}j."
        )

    def params_grid(self) -> list[dict]:
        """Grille de sensibilité : surtout le seuil RSI."""
        return [
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 5.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 15.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 20.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 2.0, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 3.0, "max_days": 5},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 3},
            {"sma200_period": 200, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 7},
            {"sma200_period": 180, "sma5_period": 5, "rsi2_threshold": 10.0,
             "atr_period": 14, "stop_atr_factor": 2.5, "max_days": 5},
        ]
