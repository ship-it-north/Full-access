"""Contrôles qualité par symbole.

Chaque contrôle renvoie des constats explicites. Un constat `blocking=True`
signifie que la série ne doit pas servir au backtest tant que ce n'est pas
réglé — le brief interdit de continuer sur une donnée suspecte.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C


@dataclass(frozen=True)
class Finding:
    symbol: str
    check: str
    detail: str
    count: int
    blocking: bool


def _sessions(symbol: str, start, end) -> pd.DatetimeIndex:
    """Séances attendues selon le calendrier de la bourse du symbole."""
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar(C.EXCHANGE_CALENDAR.get(symbol, "NYSE"))
    schedule = cal.schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(schedule.index).tz_localize(None).normalize()


def check_symbol(df: pd.DataFrame, symbol: str, timeframe: str) -> list[Finding]:
    findings: list[Finding] = []

    def add(check, detail, count, blocking):
        findings.append(Finding(symbol, check, detail, int(count), blocking))

    if df.empty:
        add("vide", "aucune barre", 0, True)
        return findings

    dupes = int(df.index.duplicated().sum())
    if dupes:
        add("doublons", "horodatages dupliqués", dupes, True)
    if not df.index.is_monotonic_increasing:
        add("ordre", "index non trié", 1, True)

    bad_ohlc = (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    ).sum()
    if bad_ohlc:
        add("ohlc_incoherent", "high/low hors bornes open/close", bad_ohlc, True)

    non_positive = (df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()
    if non_positive:
        add("prix_non_positif", "prix <= 0", non_positive, True)

    zero_volume = int((df["volume"] <= 0).sum())
    if zero_volume:
        add("volume_nul", "barres à volume nul", zero_volume,
            zero_volume > 0.05 * len(df))

    returns = np.log(df["close"]).diff()
    jumps = int((returns.abs() > np.log(1 + C.MAX_DAILY_MOVE)).sum())
    if jumps:
        add("saut_suspect", f"variations > {C.MAX_DAILY_MOVE:.0%} entre deux barres "
            "(fractionnement non ajusté ?)", jumps, False)

    stale = int((df[["open", "high", "low", "close"]].diff().abs().sum(axis=1) == 0).sum())
    if stale > 0.01 * len(df):
        add("barres_figees", "barres OHLC identiques à la précédente", stale, False)

    if timeframe == "1d":
        expected = _sessions(symbol, df.index[0], df.index[-1])
        missing = expected.difference(df.index)
        if len(missing):
            rate = len(missing) / max(len(expected), 1)
            add("seances_manquantes",
                f"{rate:.2%} des séances attendues absentes "
                f"(ex. {', '.join(str(d.date()) for d in missing[:3])})",
                len(missing), rate > C.MAX_MISSING_SESSION_RATE)
        extra = df.index.difference(expected)
        if len(extra):
            add("seances_inattendues", "barres hors calendrier de la bourse", len(extra), False)

    return findings


def quality_report(data: dict[str, pd.DataFrame], timeframe: str) -> pd.DataFrame:
    rows = []
    for symbol, df in data.items():
        for f in check_symbol(df, symbol, timeframe):
            rows.append({"symbole": f.symbol, "controle": f.check, "detail": f.detail,
                         "occurrences": f.count, "bloquant": f.blocking})
    return pd.DataFrame(rows, columns=["symbole", "controle", "detail", "occurrences", "bloquant"])


def coverage(data: dict[str, pd.DataFrame], timeframe: str) -> pd.DataFrame:
    rows = []
    for symbol, df in data.items():
        if df.empty:
            continue
        years = (df.index[-1] - df.index[0]).days / 365.25
        rows.append({
            "symbole": symbol,
            "barres": len(df),
            "debut": str(df.index[0])[:10],
            "fin": str(df.index[-1])[:10],
            "annees": round(years, 2),
            "prix_dernier": round(float(df["close"].iloc[-1]), 2),
            "devise": C.CURRENCY.get(symbol, "USD"),
        })
    return pd.DataFrame(rows).sort_values("symbole")
