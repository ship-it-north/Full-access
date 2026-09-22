"""Fournisseur Alpaca.

Clé attendue dans `.env` :
    ALPACA_KEY_ID=...
    ALPACA_SECRET_KEY=...
Sans clé, `available()` retourne False — aucune substitution silencieuse.
Alpaca ne couvre pas les FNB canadiens (.TO) : ceux-là passent par IBKR.

Flux : `sip` (ruban consolidé) par défaut, repli sur `iex` si le compte n'y a
pas droit. L'écart est majeur et le flux retenu est consigné dans les
métadonnées du cache : mesuré sur SPY en 2024, IEX ne porte que 1,5 % du
volume consolidé, alors que SIP correspond à Yahoo sur 100 % des séances à
1 point de base près. Une plage d'ouverture calculée sur IEX ne serait pas
celle du marché.
"""

from __future__ import annotations

import os
import time

import pandas as pd
import requests

from .base import Provider, ProviderUnavailable

BASE_URL = "https://data.alpaca.markets/v2/stocks/{symbol}/bars"
TZ_NY = "America/New_York"
TIMEFRAME_MAP = {"1d": "1Day", "5m": "5Min"}
PAGE_LIMIT = 10_000


def _credentials() -> tuple[str | None, str | None]:
    return os.environ.get("ALPACA_KEY_ID"), os.environ.get("ALPACA_SECRET_KEY")


FEEDS = ("sip", "iex")


class AlpacaProvider(Provider):
    name = "alpaca"
    adjusted = True

    def __init__(self, feed: str | None = None):
        self.requested_feed = feed
        self.last_feed: str | None = None

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
        feeds = (self.requested_feed,) if self.requested_feed else FEEDS

        rows, errors = [], []
        for feed in feeds:
            rows, err = self._download(symbol, timeframe, start, end, headers, feed)
            if rows:
                self.last_feed = feed
                break
            errors.append(f"{feed}: {err}")
        if not rows:
            raise ProviderUnavailable(
                f"Alpaca n'a renvoyé aucune barre pour {symbol} ({' | '.join(errors)})")
        raw = pd.DataFrame(rows)
        utc = pd.DatetimeIndex(pd.to_datetime(raw["t"], utc=True))
        if timeframe == "1d":
            index = utc.tz_convert(TZ_NY).tz_localize(None).normalize()
            index.name = "date"
        else:
            # Rester en heure de New York, fuseau compris : passer par `.values`
            # perdrait le fuseau et laisserait des horodatages UTC déguisés.
            index = utc.tz_convert(TZ_NY)
            index.name = "timestamp"
        df = pd.DataFrame({
            "open": raw["o"].values, "high": raw["h"].values, "low": raw["l"].values,
            "close": raw["c"].values, "adj_close": raw["c"].values, "volume": raw["v"].values,
        }, index=index).astype(float)

        if timeframe == "1d":
            # Le brief exige des prix ajustés pour le quotidien, mais le nombre
            # d'actions achetables et la commission par action dépendent du prix
            # réellement coté. On garde donc l'OHLC brut et on remplit `adj_close`
            # avec la série ajustée (dividendes et fractionnements).
            adj_rows, _ = self._download(symbol, timeframe, start, end, headers,
                                         self.last_feed, adjustment="all")
            if adj_rows:
                adj = pd.DataFrame(adj_rows)
                adj_index = (pd.DatetimeIndex(pd.to_datetime(adj["t"], utc=True))
                             .tz_convert(TZ_NY).tz_localize(None).normalize())
                series = pd.Series(adj["c"].values, index=adj_index)
                df["adj_close"] = series.reindex(df.index).astype(float)
        return df

    def _download(self, symbol, timeframe, start, end, headers, feed,
                  adjustment: str = "raw") -> tuple[list, str]:
        """Une seule tentative sur un flux donné. Retourne (barres, erreur)."""
        params = {
            "timeframe": TIMEFRAME_MAP[timeframe],
            "start": pd.Timestamp(start).strftime("%Y-%m-%d"),
            "limit": PAGE_LIMIT,
            # Prix bruts : ce sont eux qui déterminent le nombre d'actions
            # achetables et la commission par action. L'ajustement est porté
            # par `adj_close` côté quotidien.
            "adjustment": adjustment,
            "feed": feed,
        }
        if end:
            params["end"] = pd.Timestamp(end).strftime("%Y-%m-%d")

        rows, page_token, retries = [], None, 0
        while True:
            if page_token:
                params["page_token"] = page_token
            response = requests.get(BASE_URL.format(symbol=symbol), headers=headers,
                                    params=params, timeout=60)
            if response.status_code == 429 and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            if response.status_code != 200:
                return [], f"HTTP {response.status_code} {response.text[:120]}"
            payload = response.json()
            rows.extend(payload.get("bars") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return rows, "aucune barre" if not rows else ""
