"""Téléchargement ccxt (Bybit perps USDT) avec cache parquet local.

Aucune clé API : uniquement des endpoints publics. La pagination respecte la
limite de 1000 bougies par appel et le rate limit de l'exchange.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

import config as C


def get_exchange():
    import os

    import ccxt

    ex = getattr(ccxt, C.EXCHANGE_ID)({
        "enableRateLimit": True,
        "options": {"defaultType": C.MARKET_TYPE},
    })
    # ccxt passe `verify=self.verify and self.validateServerSsl` à requests, ce qui
    # écrase REQUESTS_CA_BUNDLE : derrière un proxy TLS il faut renseigner les deux
    # attributs pour que le chemin du bundle survive au `and`.
    bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if bundle and Path(bundle).exists():
        ex.verify = bundle
        ex.validateServerSsl = bundle
    ex.load_markets()
    return ex


def _is_eligible(market: dict) -> bool:
    if not market.get("swap") or not market.get("active"):
        return False
    if market.get("quote") != C.QUOTE or not market.get("linear"):
        return False
    if market.get("expiry"):  # exclut les futures datées
        return False
    base = (market.get("base") or "").upper()
    if base in C.STABLE_BASES or base in C.NON_CRYPTO_BASES:
        return False
    return not any(base.endswith(p) for p in C.LEVERAGED_PATTERNS)


def _quote_volume(ticker: dict) -> float | None:
    """Volume 24h en quote. Les champs diffèrent d'un exchange à l'autre."""
    candidates = [ticker.get("quoteVolume")]
    info = ticker.get("info") or {}
    candidates += [info.get(k) for k in ("turnover24h", "quoteVolume24h", "volCcyQuote24h")]
    for value in candidates:
        try:
            volume = float(value)
        except (TypeError, ValueError):
            continue
        if volume > 0:
            return volume
    # Repli : volume en base × dernier prix.
    try:
        return float(ticker["baseVolume"]) * float(ticker["last"])
    except (TypeError, ValueError, KeyError):
        return None


def select_universe(exchange, size: int = C.UNIVERSE_SIZE) -> list[str]:
    """Les `size` perps USDT au plus gros volume 24h (hors stables et tokens à levier)."""
    tickers = exchange.fetch_tickers()
    rows = []
    for symbol, ticker in tickers.items():
        market = exchange.markets.get(symbol)
        if market is None or not _is_eligible(market):
            continue
        volume = _quote_volume(ticker)
        if volume is None:
            continue
        rows.append((symbol, volume))
    rows.sort(key=lambda r: r[1], reverse=True)
    return [symbol for symbol, _ in rows[:size]]


def _cache_path(symbol: str) -> Path:
    safe = symbol.replace("/", "_").replace(":", "_")
    return C.DATA_DIR / f"{C.EXCHANGE_ID}_{safe}_{C.TIMEFRAME}.parquet"


def _fetch_page(exchange, symbol: str, since: int) -> list[list]:
    for attempt in range(C.MAX_RETRIES):
        try:
            return exchange.fetch_ohlcv(symbol, C.TIMEFRAME, since=since, limit=C.OHLCV_LIMIT)
        except Exception as exc:  # réseau, rate limit, maintenance
            if attempt == C.MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"    retry {symbol} dans {wait}s ({type(exc).__name__}: {exc})")
            time.sleep(wait)
    return []


def fetch_ohlcv(exchange, symbol: str, since_ms: int, until_ms: int) -> pd.DataFrame:
    """Pagination complète entre deux bornes, 1000 bougies par appel."""
    rows: list[list] = []
    cursor = since_ms
    last_seen = -1
    probe_step = 30 * 24 * C.BAR_MS
    while cursor < until_ms:
        page = _fetch_page(exchange, symbol, cursor)
        if not page:
            if rows:
                break
            # Paire listée après `since_ms` : on avance par pas de 30 jours
            # jusqu'à trouver le début de l'historique.
            cursor += probe_step
            continue
        rows.extend(page)
        last = page[-1][0]
        if last <= last_seen:  # plus de progression : fin de l'historique disponible
            break
        last_seen = last
        cursor = last + C.BAR_MS
        if last >= until_ms - C.BAR_MS:
            break
        time.sleep(C.RATE_LIMIT_SLEEP)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.drop(columns="ts").set_index("timestamp").sort_index()
    return df[~df.index.duplicated(keep="last")].astype(float)


def load_pair(exchange, symbol: str, start: str = C.START_DATE, refresh: bool = True) -> pd.DataFrame:
    """Charge depuis le cache parquet et ne télécharge que les barres manquantes."""
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol)
    cached = pd.read_parquet(path) if path.exists() else None

    start_ms = int(pd.Timestamp(start).timestamp() * 1000)
    now_ms = int(time.time() * 1000)

    if cached is not None and not cached.empty:
        if not refresh:
            return cached
        last_ms = int(cached.index[-1].timestamp() * 1000)
        if now_ms - last_ms < 2 * C.BAR_MS:
            return cached
        fresh = fetch_ohlcv(exchange, symbol, last_ms + C.BAR_MS, now_ms)
        if fresh.empty:
            return cached
        merged = pd.concat([cached, fresh])
        merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    else:
        merged = fetch_ohlcv(exchange, symbol, start_ms, now_ms)
        if merged.empty:
            return merged

    merged.to_parquet(path)
    return merged


def load_universe(
    symbols: list[str] | None = None,
    size: int = C.UNIVERSE_SIZE,
    refresh: bool = True,
    offline: bool = False,
    workers: int = 1,
) -> dict[str, pd.DataFrame]:
    """Retourne {symbole: OHLCV}. En mode offline, lit uniquement le cache parquet."""
    if offline:
        out = {}
        for path in sorted(C.DATA_DIR.glob(f"{C.EXCHANGE_ID}_*_{C.TIMEFRAME}.parquet")):
            symbol = path.stem[len(C.EXCHANGE_ID) + 1:-len(C.TIMEFRAME) - 1]
            out[symbol] = pd.read_parquet(path)
        return out

    exchange = get_exchange()
    symbols = symbols or select_universe(exchange, size)
    out: dict[str, pd.DataFrame] = {}

    if workers <= 1:
        for n, symbol in enumerate(symbols, 1):
            print(f"[{n}/{len(symbols)}] {symbol}")
            df = load_pair(exchange, symbol, refresh=refresh)
            if not df.empty:
                out[symbol] = df
                print(f"    {len(df)} barres, {df.index[0].date()} -> {df.index[-1].date()}")
        return out

    # Une instance ccxt par thread : le limiteur de débit n'est pas thread-safe.
    local = threading.local()

    def worker(symbol: str) -> tuple[str, pd.DataFrame]:
        if not hasattr(local, "exchange"):
            local.exchange = get_exchange()
        return symbol, load_pair(local.exchange, symbol, refresh=refresh)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, s): s for s in symbols}
        for n, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            try:
                symbol, df = future.result()
            except Exception as exc:
                print(f"[{n}/{len(symbols)}] {symbol} ECHEC : {type(exc).__name__}: {exc}")
                continue
            if df.empty:
                print(f"[{n}/{len(symbols)}] {symbol} aucune donnée")
                continue
            out[symbol] = df
            print(f"[{n}/{len(symbols)}] {symbol} {len(df)} barres, "
                  f"{df.index[0].date()} -> {df.index[-1].date()}", flush=True)
    return dict(sorted(out.items()))
