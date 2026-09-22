"""Phase A — collecte, contrôle qualité et rapport.

    python -m data.fetch --daily                 # quotidien 10 ans via la meilleure source
    python -m data.fetch --daily --provider ibkr # force IBKR (nécessite TWS papier)
    python -m data.fetch --intraday              # barres 5 min (IBKR ou Alpaca requis)
    python -m data.fetch --events                # events.csv depuis Fed et BLS

Aucune donnée n'est inventée : si une source est indisponible, le symbole est
laissé absent et l'échec est consigné dans le rapport.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import cache, config as C, events as EV, quality, universe
from .providers.alpaca import AlpacaProvider
from .providers.base import ProviderUnavailable
from .providers.ibkr import IBKRProvider
from .providers.yahoo import YahooProvider

PROVIDERS = {"ibkr": IBKRProvider, "alpaca": AlpacaProvider, "yahoo": YahooProvider}
# Ordre de préférence du brief : IBKR d'abord, puis les secours.
DAILY_ORDER = ["ibkr", "alpaca", "yahoo"]
INTRADAY_ORDER = ["ibkr", "alpaca"]


def fetch_symbol(symbol: str, timeframe: str, start: str, order: list[str]) -> tuple[str, str]:
    """Essaie les fournisseurs dans l'ordre. Retourne (fournisseur, message)."""
    attempts = []
    for name in order:
        provider = PROVIDERS[name]()
        ok, reason = provider.available()
        if not ok:
            attempts.append(f"{name}: {reason}")
            continue
        try:
            df = provider.fetch(symbol, timeframe, start)
        except (ProviderUnavailable, Exception) as exc:  # noqa: BLE001
            attempts.append(f"{name}: {type(exc).__name__}: {exc}")
            continue
        feed = getattr(provider, "last_feed", None)
        note = " | ".join(attempts)
        if feed:
            note = f"flux={feed}" + (f" | {note}" if note else "")
        cache.save(df, symbol, timeframe, provider.name, C.CURRENCY.get(symbol, "USD"),
                   provider.adjusted, note=note)
        return name, f"{len(df)} barres" + (f" (flux {feed})" if feed else "")
    return "", " | ".join(attempts)


def run(timeframes: list[str], symbols: list[str], order_override: str | None = None) -> dict:
    results: dict[str, dict[str, str]] = {}
    for timeframe in timeframes:
        start = C.DAILY_START if timeframe == "1d" else C.INTRADAY_START
        order = ([order_override] if order_override
                 else (DAILY_ORDER if timeframe == "1d" else INTRADAY_ORDER))
        results[timeframe] = {}
        for symbol in symbols:
            provider, message = fetch_symbol(symbol, timeframe, start, order)
            results[timeframe][symbol] = f"{provider or 'ÉCHEC'} — {message}"
            print(f"  [{timeframe}] {symbol:<9} {results[timeframe][symbol]}", flush=True)
    return results


def build_events(history_from: int = 2013) -> tuple[pd.DataFrame, list[str]]:
    problems: list[str] = []
    try:
        fomc, warnings = EV.fetch_fomc(history_from=history_from)
        problems += warnings
    except EV.SourceUnavailable as exc:
        fomc = []
        problems.append(f"FOMC : {exc}")

    years = list(range(history_from, pd.Timestamp.now('UTC').year + 2))
    try:
        bls = EV.fetch_bls(years)
    except EV.SourceUnavailable as exc:
        bls = []
        problems.append(f"IPC et EMPLOI : {exc}")

    all_events = fomc + bls
    if all_events:
        EV.write_events_csv(all_events, C.EVENTS_CSV, missing=problems)
    return EV.to_dataframe(all_events), problems


def report(fetch_results: dict, events_df: pd.DataFrame, event_problems: list[str]) -> Path:
    C.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    daily = cache.load_many(C.CANDIDATE_UNIVERSE, "1d")
    intraday = cache.load_many(C.CANDIDATE_UNIVERSE, "5m")

    cov = quality.coverage(daily, "1d")
    qc = quality.quality_report(daily, "1d")
    cov_intra = quality.coverage(intraday, "5m")
    qc_intra = quality.quality_report(intraday, "5m")
    afford = universe.affordability(daily)
    inv = cache.inventory()

    blocking = qc[qc["bloquant"]] if not qc.empty else qc
    lines = [
        "# Phase A — Données : rapport",
        "",
        f"Généré le {pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M')} UTC.",
        "",
        "## 1. Ce qui a été collecté",
        "",
        inv.to_markdown(index=False) if not inv.empty else "_cache vide_",
        "",
        "## 2. Couverture (quotidien)",
        "",
        cov.to_markdown(index=False) if not cov.empty else "_aucune série quotidienne_",
        "",
        "## 3. Contrôles qualité",
        "",
        (f"{len(blocking)} constat(s) bloquant(s) sur {len(qc)}." if not qc.empty
         else "Aucun constat."),
        "",
        qc.to_markdown(index=False) if not qc.empty else "",
        "",
        "## 4. Éligibilité avec 200 $ CAD",
        "",
        "`tradable_actions_entieres` exige : au moins 1 action achetable, un risque "
        "inférieur à 5 $ pour 1 action avec un stop à 2 %, et une liquidité suffisante.",
        "",
        afford.to_markdown(index=False) if not afford.empty else "_n/a_",
        "",
        f"**Retenus : {', '.join(universe.selected(afford)) or 'aucun'}**",
        "",
        "## 5. Barres 5 minutes (ORB)",
        "",
        (f"{len(intraday)} symbole(s) en cache." if intraday else
         "**Aucune.** Yahoo ne sert que 60 jours en 5 min ; IBKR et Alpaca exigent "
         "respectivement TWS papier et une clé API. L'ORB ne peut pas être évalué "
         "tant que cette source n'est pas branchée."),
        "",
        cov_intra.to_markdown(index=False) if not cov_intra.empty else "",
        "",
        ("Flux **SIP** (ruban consolidé) et non IEX. Mesuré sur SPY en 2024 : IEX ne "
         "porte que 1,5 % du volume consolidé, tandis que SIP correspond aux prix "
         "Yahoo sur 100 % des séances à 1 point de base près. Une plage d'ouverture "
         "calculée sur IEX ne serait pas celle du marché." if intraday else ""),
        "",
        (qc_intra.to_markdown(index=False) if not qc_intra.empty else
         ("Aucun constat sur l'intraday." if intraday else "")),
        "",
        ("Les barres couvrent aussi la pré-séance et l'après-séance (4h00 à 20h00 ET) ; "
         "le moteur filtrera la séance régulière. Les contrôles ci-dessus ne portent "
         "que sur 9h30-16h00." if intraday else ""),
        "",
        "## 6. Événements macro",
        "",
        (f"{len(events_df)} événements écrits dans `events.csv`." if len(events_df)
         else "_aucun événement_"),
        "",
        (events_df.groupby("label").agg(n=("datetime", "size"),
                                        premier=("datetime", "min"),
                                        dernier=("datetime", "max")).reset_index()
         .to_markdown(index=False) if len(events_df) else ""),
        "",
        "Limite connue : seules les 8 réunions régulières par an sont extraites. "
        "Les réunions d'urgence (3 et 15 mars 2020) ne figurent pas dans les listes "
        "de calendrier de la Fed sous une forme exploitable automatiquement.",
        "",
    ]
    if event_problems:
        lines += ["### Sources indisponibles", "",
                  *[f"- {p}" for p in event_problems], ""]
    lines += ["## 7. Journal de collecte", ""]
    for timeframe, rows in fetch_results.items():
        lines += [f"### {timeframe}", ""]
        lines += [f"- `{s}` : {msg}" for s, msg in rows.items()]
        lines += [""]

    path = C.REPORTS_DIR / "phase_a_donnees.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    if not qc.empty:
        qc.to_csv(C.REPORTS_DIR / "phase_a_qualite.csv", index=False)
    if not afford.empty:
        afford.to_csv(C.REPORTS_DIR / "phase_a_eligibilite.csv", index=False)
    if not qc_intra.empty:
        qc_intra.to_csv(C.REPORTS_DIR / "phase_a_qualite_5m.csv", index=False)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase A — collecte des données")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--intraday", action="store_true")
    ap.add_argument("--events", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--provider", choices=list(PROVIDERS), default=None)
    ap.add_argument("--symbols", nargs="*", default=C.CANDIDATE_UNIVERSE)
    args = ap.parse_args()

    do_daily = args.daily or args.all
    do_intraday = args.intraday or args.all
    do_events = args.events or args.all
    if not (do_daily or do_intraday or do_events):
        ap.error("préciser --daily, --intraday, --events ou --all")

    timeframes = (["1d"] if do_daily else []) + (["5m"] if do_intraday else [])
    results = run(timeframes, args.symbols, args.provider) if timeframes else {}

    events_df, problems = (build_events() if do_events else (pd.DataFrame(), []))
    for p in problems:
        print(f"  ! {p}")

    path = report(results, events_df, problems)
    print(f"\nRapport : {path}")


if __name__ == "__main__":
    main()
