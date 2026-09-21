"""Dates d'événements macro, depuis les sources officielles uniquement.

FOMC : federalreserve.gov (calendriers publiés, y compris les archives).
IPC et emploi : bls.gov. Le brief interdit de deviner ces dates ; si une source
est injoignable, on lève et on le signale au lieu d'écrire une valeur approchée.

Heures : le brief demande l'heure de New York. Les heures de publication sont
des conventions stables et documentées par l'émetteur :
  - FOMC : communiqué à 14 h 00 ET les jours de décision (2e jour de réunion).
  - BLS (IPC, emploi) : 8 h 30 ET.
Ces heures sont des constantes déclarées ici, pas des dates devinées.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
import requests

FED_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
FED_HISTORICAL_URL = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
BLS_SCHEDULE_URL = "https://www.bls.gov/schedule/news_release/{year}_sched.htm"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

FOMC_RELEASE_TIME = "14:00"
BLS_RELEASE_TIME = "08:30"

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


class SourceUnavailable(RuntimeError):
    """La source officielle n'a pas pu être lue. On ne substitue rien."""


@dataclass(frozen=True)
class Event:
    datetime_ny: pd.Timestamp
    window_min: int
    label: str
    source: str


def _get(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
    if response.status_code != 200:
        raise SourceUnavailable(f"{url} a répondu {response.status_code}")
    return response.text


ABBREV = {m[:3]: i for m, i in MONTHS.items()}
ALL_MONTHS = {**MONTHS, **ABBREV}
MONTH_RE = "|".join(sorted(ALL_MONTHS, key=len, reverse=True))


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def parse_fomc_block(text: str, year: int) -> list[pd.Timestamp]:
    """Dates de décision (dernier jour de réunion) dans le bloc d'une année.

    Trois écritures coexistent sur le site de la Fed :
      « January 27-28 »   même mois
      « April 30-May 1 »  mois complets à cheval
      « Jan/Feb 31-1 »    abréviations à cheval (pages passées)
    La décision tombe le dernier jour. Les notes qui mentionnent une autre
    année (« scheduled for January 25-26, 2028 ») sont écartées.
    """
    text = _strip_tags(text)
    found: list[pd.Timestamp] = []
    consumed: list[tuple[int, int]] = []

    def overlaps(span):
        return any(span[0] < e and s < span[1] for s, e in consumed)

    # « Jan/Feb 31-1 » : le second mois porte la décision.
    for m in re.finditer(rf"({MONTH_RE})\s*/\s*({MONTH_RE})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})", text):
        month = ALL_MONTHS[m.group(2)]
        # Une réunion à cheval sur janvier/février d'une année civile suivante
        # reste dans l'année de la page (ex. « Jan/Feb 31-1 » de 2023).
        found.append(pd.Timestamp(year=year, month=month, day=int(m.group(4))))
        consumed.append(m.span())

    # « April 30-May 1 »
    for m in re.finditer(rf"({MONTH_RE})\s+(\d{{1,2}})\s*[-–]\s*({MONTH_RE})\s+(\d{{1,2}})", text):
        if overlaps(m.span()):
            continue
        found.append(pd.Timestamp(year=year, month=ALL_MONTHS[m.group(3)], day=int(m.group(4))))
        consumed.append(m.span())

    # « January 27-28 » — en excluant ce qui est suivi d'une autre année.
    for m in re.finditer(rf"({MONTH_RE})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})(\s*,\s*(\d{{4}}))?", text):
        if overlaps(m.span()):
            continue
        if m.group(5) and int(m.group(5)) != year:
            continue
        found.append(pd.Timestamp(year=year, month=ALL_MONTHS[m.group(1)], day=int(m.group(3))))
        consumed.append(m.span())

    return sorted(set(found))


def parse_fomc(html: str) -> list[pd.Timestamp]:
    """Page des calendriers courants : un bloc par année."""
    out: list[pd.Timestamp] = []
    for year_match in re.finditer(r"(\d{4})\s+FOMC\s+Meetings", html):
        year = int(year_match.group(1))
        block = html[year_match.end(): year_match.end() + 20000]
        block = re.split(r"\d{4}\s+FOMC\s+Meetings", block)[0]
        out += parse_fomc_block(block, year)
    return sorted(set(out))


def fetch_fomc(history_from: int | None = None) -> tuple[list[Event], list[str]]:
    """Calendriers courants + pages d'archives par année. Retourne (événements, alertes)."""
    dates = set(parse_fomc(_get(FED_CALENDAR_URL)))
    sources = {FED_CALENDAR_URL}
    warnings: list[str] = []

    if history_from is not None:
        current = min(d.year for d in dates) if dates else pd.Timestamp.utcnow().year
        for year in range(history_from, current):
            url = FED_HISTORICAL_URL.format(year=year)
            try:
                found = parse_fomc_block(_get(url), year)
            except SourceUnavailable as exc:
                warnings.append(f"archive {year} illisible : {exc}")
                continue
            if not found:
                warnings.append(f"archive {year} : aucune date extraite")
            dates.update(found)
            sources.add(url)

    if not dates:
        raise SourceUnavailable("aucune date FOMC extraite des pages de la Fed")

    # Le FOMC tient 8 réunions régulières par an ; un écart signale un parsing
    # incomplet (ou des réunions d'urgence, comme en mars 2020).
    by_year: dict[int, int] = {}
    for d in dates:
        by_year[d.year] = by_year.get(d.year, 0) + 1
    for year, count in sorted(by_year.items()):
        if count < 8:
            warnings.append(f"{year} : {count} réunions extraites au lieu de 8 attendues")

    events = [Event(pd.Timestamp(f"{d.date()} {FOMC_RELEASE_TIME}"), 60, "FOMC",
                    FED_CALENDAR_URL) for d in sorted(dates)]
    return events, warnings


def parse_bls(html: str, year: int) -> list[tuple[pd.Timestamp, str]]:
    """Dates IPC et emploi depuis la page de calendrier BLS d'une année."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S)
    out = []
    for row in rows:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)]
        if len(cells) < 2:
            continue
        title = cells[0]
        label = None
        if re.search(r"Consumer Price Index", title, re.I):
            label = "IPC"
        elif re.search(r"Employment Situation", title, re.I):
            label = "EMPLOI"
        if not label:
            continue
        for cell in cells[1:]:
            m = re.search(rf"({'|'.join(MONTHS)})\s+(\d{{1,2}}),?\s*(\d{{4}})?", cell)
            if m:
                y = int(m.group(3) or year)
                out.append((pd.Timestamp(year=y, month=MONTHS[m.group(1)], day=int(m.group(2))),
                            label))
                break
    return out


def fetch_bls(years: list[int]) -> list[Event]:
    events, errors = [], []
    for year in years:
        url = BLS_SCHEDULE_URL.format(year=year)
        try:
            for date, label in parse_bls(_get(url), year):
                events.append(Event(pd.Timestamp(f"{date.date()} {BLS_RELEASE_TIME}"),
                                    30, label, url))
        except SourceUnavailable as exc:
            errors.append(str(exc))
    if not events:
        raise SourceUnavailable(
            "calendriers BLS inaccessibles depuis cette machine : " + " ; ".join(errors)
        )
    return events


def to_dataframe(events: list[Event]) -> pd.DataFrame:
    rows = [{"datetime": e.datetime_ny.strftime("%Y-%m-%d %H:%M"),
             "window_min": e.window_min, "label": e.label, "source": e.source}
            for e in sorted(events, key=lambda e: e.datetime_ny)]
    return pd.DataFrame(rows, columns=["datetime", "window_min", "label", "source"])


def write_events_csv(events: list[Event], path, missing: list[str] | None = None) -> pd.DataFrame:
    """Écrit events.csv au format attendu par run.py, avec la provenance en commentaire."""
    df = to_dataframe(events)
    lines = ["# Dates issues des sources officielles. Ne pas éditer à la main sans noter la source.",
             f"# Généré le {pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M')} UTC.",
             "# FOMC : communiqué à 14:00 ET. BLS (IPC, EMPLOI) : 08:30 ET.",
             "# Heures de New York."]
    for item in missing or []:
        lines.append(f"# MANQUANT : {item}")
    header = "\n".join(lines) + "\n"
    path.write_text(header + df.drop(columns=["source"]).to_csv(index=False), encoding="utf-8")
    return df
