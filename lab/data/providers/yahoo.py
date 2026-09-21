"""Fournisseur Yahoo (yfinance).

Quotidien uniquement pour la recherche, comme le permet le brief. Yahoo ne
sert que 60 jours de barres 5 minutes : insuffisant pour l'ORB, donc l'intraday
lève `ProviderUnavailable` au lieu de renvoyer une série tronquée.
"""

from __future__ import annotations

import pandas as pd

from .base import Provider, ProviderUnavailable

YAHOO_INTRADAY_LIMIT_DAYS = 60


class YahooProvider(Provider):
    name = "yahoo"
    adjusted = True

    def available(self) -> tuple[bool, str]:
        try:
            import yfinance  # noqa: F401
        except ImportError:
            return False, "yfinance non installé"
        return True, ""

    def fetch(self, symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
        ok, reason = self.available()
        if not ok:
            raise ProviderUnavailable(reason)
        if timeframe != "1d":
            raise ProviderUnavailable(
                f"Yahoo ne fournit que {YAHOO_INTRADAY_LIMIT_DAYS} jours en {timeframe} — "
                "insuffisant pour les 3 ans exigés par l'ORB. Utiliser IBKR ou Alpaca."
            )
        import yfinance as yf

        raw = yf.download(symbol, start=start, end=end, interval="1d",
                          auto_adjust=False, progress=False, threads=False)
        if raw.empty:
            raise ProviderUnavailable(f"Yahoo n'a renvoyé aucune barre pour {symbol}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        df = pd.DataFrame({
            "open": raw["Open"], "high": raw["High"], "low": raw["Low"],
            "close": raw["Close"], "adj_close": raw["Adj Close"], "volume": raw["Volume"],
        })
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df.index.name = "date"
        return df.dropna(subset=["open", "high", "low", "close"]).astype(float)
