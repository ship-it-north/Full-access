"""Fournisseur Alpaca (source de secours pour les barres 5 minutes).

Clé gratuite (données IEX) attendue dans `.env` :
    ALPACA_KEY_ID=...
    ALPACA_SECRET_KEY=...
Sans clé, `available()` retourne False — aucune substitution silencieuse.
Alpaca ne couvre pas les FNB canadiens (.TO) : ceux-là passent par IBKR.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

from .base import Provider, ProviderUnavailable

BASE_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
TIMEFRAME_MAP = {"1d": "1Day", "5m": "5Min"}
PAGE_LIMIT = 10_000


def _credentials() -> tuple[str | None, str | None]:
    return os.environ.get("ALPACA_KEY_ID"), os.environ.get("ALPACA_SECRET_KEY")


class AlpacaProvider(Provider):
    name = "alpaca"
    adjusted = True

    def available(self) -> tuple[bool, str]:
        key, secret = _credentials()
        if not key or not secret:
            return False, "ALPACA_KEY_ID / ALPACA_SECRET_KEY absents de l'environnement"
        return True, ""

    def fetch(self, symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
        ok, reason = self.available()
        if not ok:
            raise ProviderUnavailable(reason)
        if symbol.endswith(".TO"):
            raise ProviderUnavailable("Alpaca ne couvre pas les titres canadiens ; utiliser IBKR")
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"timeframe non supporté : {timeframe}")

        key, secret = _credentials()
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        params = {
            "timeframe": TIMEFRAME_MAP[timeframe],
            "start": pd.Timestamp(start).strftime("%Y-%m-%d"),
            "limit": PAGE_LIMIT,
            "adjustment": "all",
            "feed": "iex",
        }
        if end:
            params["end"] = pd.Timestamp(end).strftime("%Y-%m-%d")

        rows, page_token = [], None
        while True:
            if page_token:
                params["page_token"] = page_token
            response = requests.get(BASE_URL.format(symbol=symbol), headers=headers,
                                    params=params, timeout=30)
            if response.status_code == 429:
                time.sleep(2)
                continue
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("bars") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break

        if not rows:
            raise ProviderUnavailable(f"Alpaca n'a renvoyé aucune barre pour {symbol}")
        raw = pd.DataFrame(rows)
        index = pd.to_datetime(raw["t"], utc=True)
        if timeframe == "1d":
            index = index.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
            name = "date"
        else:
            index = index.dt.tz_convert("America/New_York")
            name = "timestamp"
        df = pd.DataFrame({
            "open": raw["o"].values, "high": raw["h"].values, "low": raw["l"].values,
            "close": raw["c"].values, "adj_close": raw["c"].values, "volume": raw["v"].values,
        }, index=pd.DatetimeIndex(index.values, name=name))
        return df.astype(float)
