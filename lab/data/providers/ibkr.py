"""Fournisseur IBKR via ib_insync (source principale du brief).

Ne peut pas s'exécuter sans TWS ou IB Gateway en mode papier à l'écoute
(port 7497 par défaut). Le code est écrit pour tourner sur la machine de
Philippe ; ici, `available()` retourne False et rien n'est inventé.

Limites de requêtes historiques IBKR respectées par `Pacer` :
60 requêtes par 10 minutes, et pas plus de 6 requêtes en 2 secondes.
Les barres 5 minutes sont demandées par tranches d'un mois (durée maximale
autorisée par IBKR pour cette taille de barre), le quotidien par tranches d'un an.
"""

from __future__ import annotations

import socket
import time
from collections import deque
from datetime import datetime, timedelta

import pandas as pd

from .base import Provider, ProviderUnavailable

DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 7497           # TWS papier ; IB Gateway papier = 4002
MAX_REQUESTS_PER_10MIN = 60
MAX_REQUESTS_PER_2S = 6

CHUNK = {"1d": ("1 Y", 365), "5m": ("1 M", 30)}
BAR_SIZE = {"1d": "1 day", "5m": "5 mins"}


class Pacer:
    """Limiteur de débit conforme aux règles de pacing d'IBKR."""

    def __init__(self, per_10min: int = MAX_REQUESTS_PER_10MIN, per_2s: int = MAX_REQUESTS_PER_2S):
        self.per_10min = per_10min
        self.per_2s = per_2s
        self.stamps: deque[float] = deque()

    def delay_needed(self, now: float) -> float:
        """Secondes à attendre avant d'émettre une requête à l'instant `now`."""
        while self.stamps and now - self.stamps[0] > 600:
            self.stamps.popleft()
        waits = [0.0]
        if len(self.stamps) >= self.per_10min:
            waits.append(600 - (now - self.stamps[-self.per_10min]))
        recent = [s for s in self.stamps if now - s <= 2]
        if len(recent) >= self.per_2s:
            waits.append(2 - (now - recent[-self.per_2s]))
        return max(waits)

    def acquire(self, now: float | None = None, sleep=time.sleep) -> float:
        now = time.monotonic() if now is None else now
        wait = self.delay_needed(now)
        if wait > 0:
            sleep(wait)
            now += wait
        self.stamps.append(now)
        return wait


def chunk_ranges(start: str, end: str, timeframe: str) -> list[datetime]:
    """Dates de fin de chaque tranche, de la plus ancienne à la plus récente."""
    _, days = CHUNK[timeframe]
    t0, t1 = pd.Timestamp(start).to_pydatetime(), pd.Timestamp(end).to_pydatetime()
    out, cursor = [], t0 + timedelta(days=days)
    while cursor < t1:
        out.append(cursor)
        cursor += timedelta(days=days)
    out.append(t1)
    return out


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class IBKRProvider(Provider):
    name = "ibkr"
    adjusted = False  # TRADES non ajusté ; ADJUSTED_LAST pour le quotidien ajusté

    def __init__(self, host: str = DEFAULT_HOST, port: int = PAPER_PORT, client_id: int = 17):
        self.host, self.port, self.client_id = host, port, client_id
        self.pacer = Pacer()
        self._ib = None

    def available(self) -> tuple[bool, str]:
        try:
            import ib_insync  # noqa: F401
        except ImportError:
            return False, "ib_insync non installé"
        if not port_open(self.host, self.port):
            return False, (f"aucun TWS/IB Gateway à l'écoute sur {self.host}:{self.port} — "
                           "lancer TWS en mode papier et activer l'API")
        return True, ""

    def connect(self):
        ok, reason = self.available()
        if not ok:
            raise ProviderUnavailable(reason)
        from ib_insync import IB

        ib = IB()
        ib.connect(self.host, self.port, clientId=self.client_id, readonly=True)
        self._ib = ib
        return ib

    def _contract(self, symbol: str):
        from ib_insync import Stock

        if symbol.endswith(".TO"):
            return Stock(symbol[:-3], "TSE", "CAD")
        return Stock(symbol, "SMART", "USD", primaryExchange="ARCA")

    def fetch(self, symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
        if timeframe not in BAR_SIZE:
            raise ValueError(f"timeframe non supporté : {timeframe}")
        ib = self._ib or self.connect()
        contract = ib.qualifyContracts(self._contract(symbol))[0]
        end = end or datetime.now().strftime("%Y-%m-%d")
        duration, _ = CHUNK[timeframe]
        # ADJUSTED_LAST applique dividendes et fractionnements (exigé pour le quotidien).
        what = "ADJUSTED_LAST" if timeframe == "1d" else "TRADES"

        frames = []
        for chunk_end in chunk_ranges(start, end, timeframe):
            self.pacer.acquire()
            bars = ib.reqHistoricalData(
                contract, endDateTime=chunk_end.strftime("%Y%m%d %H:%M:%S"),
                durationStr=duration, barSizeSetting=BAR_SIZE[timeframe],
                whatToShow=what, useRTH=True, formatDate=1,
            )
            if bars:
                frames.append(pd.DataFrame(bars))
        if not frames:
            raise ProviderUnavailable(f"IBKR n'a renvoyé aucune barre pour {symbol}")

        raw = pd.concat(frames).drop_duplicates(subset="date").sort_values("date")
        index = pd.DatetimeIndex(pd.to_datetime(raw["date"]))
        if timeframe == "1d":
            index = index.tz_localize(None) if index.tz is not None else index
            index = index.normalize()
            index.name = "date"
        else:
            # `.values` perdrait le fuseau : on garde un index conscient du fuseau.
            index = (index.tz_convert("America/New_York") if index.tz is not None
                     else index.tz_localize("America/New_York"))
            index.name = "timestamp"
        df = pd.DataFrame({
            "open": raw["open"].values, "high": raw["high"].values, "low": raw["low"].values,
            "close": raw["close"].values, "adj_close": raw["close"].values,
            "volume": raw["volume"].values,
        }, index=index)
        return df.astype(float)
