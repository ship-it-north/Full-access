"""Cache parquet avec métadonnées de provenance.

Chaque série est stockée avec un fichier `.meta.json` qui consigne la source,
la date de téléchargement et si les prix sont ajustés. Le brief exige de
toujours consigner la source utilisée ; sans métadonnée, la série est
considérée comme inutilisable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config as C

# Colonnes stockées. `close` est le prix réellement traité (donc celui qui
# détermine le nombre d'actions achetables avec 200 $ et la commission par
# action) ; `adj_close` sert aux calculs de rendement.
COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


@dataclass(frozen=True)
class Meta:
    symbol: str
    timeframe: str
    provider: str
    currency: str
    adjusted: bool
    rows: int
    first: str
    last: str
    fetched_at: str
    note: str = ""


def _paths(symbol: str, timeframe: str) -> tuple[Path, Path]:
    safe = symbol.replace("/", "_")
    base = C.CACHE_DIR / safe
    return base / f"{timeframe}.parquet", base / f"{timeframe}.meta.json"


def save(df: pd.DataFrame, symbol: str, timeframe: str, provider: str,
         currency: str, adjusted: bool, note: str = "") -> Meta:
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{symbol} {timeframe}: colonnes manquantes {missing}")
    df = df[COLUMNS].sort_index()
    df = df[~df.index.duplicated(keep="last")]

    data_path, meta_path = _paths(symbol, timeframe)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(data_path)
    meta = Meta(
        symbol=symbol, timeframe=timeframe, provider=provider, currency=currency,
        adjusted=adjusted, rows=len(df),
        first=str(df.index[0]), last=str(df.index[-1]),
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note=note,
    )
    meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
    return meta


def load(symbol: str, timeframe: str) -> tuple[pd.DataFrame, Meta] | None:
    """Retourne (données, métadonnées) ou None. Une série sans métadonnée est refusée."""
    data_path, meta_path = _paths(symbol, timeframe)
    if not data_path.exists() or not meta_path.exists():
        return None
    df = pd.read_parquet(data_path)
    meta = Meta(**json.loads(meta_path.read_text(encoding="utf-8")))
    return df, meta


def load_many(symbols: list[str], timeframe: str) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol in symbols:
        got = load(symbol, timeframe)
        if got is not None:
            out[symbol] = got[0]
    return out


def inventory(timeframe: str | None = None) -> pd.DataFrame:
    """Tout ce qui est en cache, avec sa provenance."""
    rows = []
    for meta_path in sorted(C.CACHE_DIR.glob("*/*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if timeframe is None or meta["timeframe"] == timeframe:
            rows.append(meta)
    return pd.DataFrame(rows)
