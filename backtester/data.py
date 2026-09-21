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


# --------------------------------------------------------------------------- #
# Funding et univers point-in-time (phase ensemble)
# --------------------------------------------------------------------------- #
def fetch_funding_history(exchange, symbol: str, since_ms: int) -> pd.Series:
    """Historique des funding rates, paginé vers l'arrière (100 points par appel)."""
    rows: list[tuple[int, float]] = []
    cursor: int | None = None
    seen: set[int] = set()
    while True:
        params = {"after": cursor} if cursor else {}
        for attempt in range(C.MAX_RETRIES):
            try:
                page = exchange.fetch_funding_rate_history(symbol, limit=100, params=params)
                break
            except Exception:
                if attempt == C.MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
        if not page:
            break
        new = [(p["timestamp"], float(p["fundingRate"])) for p in page if p["timestamp"] not in seen]
        if not new:
            break
        seen.update(ts for ts, _ in new)
        rows.extend(new)
        oldest = min(ts for ts, _ in new)
        if oldest <= since_ms:
            break
        cursor = oldest
        time.sleep(C.RATE_LIMIT_SLEEP)
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series(dict(rows)).sort_index()
    s.index = pd.to_datetime(s.index, unit="ms", utc=True)
    return s[s.index >= pd.Timestamp(since_ms, unit="ms", tz="UTC")]


def load_funding(symbols: list[str], since: str = C.START_DATE, workers: int = 4) -> dict[str, pd.Series]:
    """Funding par paire, mis en cache en parquet."""
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    since_ms = int(pd.Timestamp(since).timestamp() * 1000)
    local = threading.local()

    def worker(symbol: str) -> tuple[str, pd.Series]:
        safe = symbol.replace("/", "_").replace(":", "_")
        path = C.DATA_DIR / f"{C.EXCHANGE_ID}_{safe}_funding.parquet"
        if path.exists():
            return symbol, pd.read_parquet(path)["funding"]
        if not hasattr(local, "exchange"):
            local.exchange = get_exchange()
        s = fetch_funding_history(local.exchange, symbol, since_ms)
        if not s.empty:
            s.rename("funding").to_frame().to_parquet(path)
        return symbol, s

    out: dict[str, pd.Series] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, s) for s in symbols]):
            try:
                symbol, s = future.result()
            except Exception as exc:
                print(f"  funding ECHEC : {type(exc).__name__}: {exc}")
                continue
            if not s.empty:
                out[symbol] = s
                print(f"  funding {symbol}: {len(s)} points", flush=True)
    return out


def load_daily_panel(symbols: list[str], since: str = C.START_DATE, workers: int = 4) -> pd.DataFrame:
    """Volume quote quotidien par paire — sert à reconstruire l'univers point-in-time."""
    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache = C.DATA_DIR / f"{C.EXCHANGE_ID}_daily_quote_volume.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    since_ms = int(pd.Timestamp(since).timestamp() * 1000)
    now_ms = int(time.time() * 1000)
    local = threading.local()
    saved_tf = C.TIMEFRAME

    def worker(symbol: str) -> tuple[str, pd.Series]:
        if not hasattr(local, "exchange"):
            local.exchange = get_exchange()
        rows: list[list] = []
        cursor, last_seen = since_ms, -1
        while cursor < now_ms:
            page = local.exchange.fetch_ohlcv(symbol, "1d", since=cursor, limit=300)
            if not page:
                cursor += 90 * 24 * C.BAR_MS
                if rows:
                    break
                continue
            rows.extend(page)
            last = page[-1][0]
            if last <= last_seen:
                break
            last_seen, cursor = last, last + 24 * C.BAR_MS
            time.sleep(C.RATE_LIMIT_SLEEP)
        if not rows:
            return symbol, pd.Series(dtype=float)
        df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "v"])
        idx = pd.to_datetime(df["ts"], unit="ms", utc=True)
        # volume quote ≈ volume base × close (comparable entre paires)
        return symbol, pd.Series((df["v"] * df["c"]).values, index=idx).groupby(level=0).last()

    series: dict[str, pd.Series] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, s) for s in symbols]):
            done += 1
            try:
                symbol, s = future.result()
            except Exception:
                continue
            if not s.empty:
                series[symbol] = s
            if done % 50 == 0:
                print(f"  daily {done}/{len(symbols)}", flush=True)
    C.TIMEFRAME = saved_tf
    panel = pd.DataFrame(series).sort_index()
    panel.to_parquet(cache)
    return panel
