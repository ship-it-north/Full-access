"""Paramètres de la couche données (phase A).

Aucune constante métier de stratégie ici : uniquement les sources, l'univers
candidat, les périodes et le format du cache.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"
REPORTS_DIR = ROOT / "reports"
EVENTS_CSV = ROOT / "events.csv"

TZ_NY = "America/New_York"

# Périodes visées (brief §5 phase A).
DAILY_START = "2013-01-01"      # 10 ans et plus
INTRADAY_START = "2016-01-04"   # profondeur réelle du flux SIP d'Alpaca (le brief en exige 3 ans)
INTRADAY_BAR = "5m"
DAILY_BAR = "1d"

# Univers candidat. La sélection finale revient au code (liquidité, écart,
# prix vs 200 $) — voir universe.py.
US_ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "XLV", "XLI", "GLD", "TLT", "EFA"]
CA_ETFS = ["XIU.TO", "ZSP.TO", "XEG.TO"]
CASH_ETFS = ["BIL", "SGOV"]      # actif « cash » du momentum
BENCHMARK = "SPY"
CANDIDATE_UNIVERSE = US_ETFS + CA_ETFS + CASH_ETFS

EXCHANGE_CALENDAR = {s: "TSX" if s.endswith(".TO") else "NYSE" for s in CANDIDATE_UNIVERSE}
CURRENCY = {s: "CAD" if s.endswith(".TO") else "USD" for s in CANDIDATE_UNIVERSE}

# Contrôles qualité
MAX_DAILY_MOVE = 0.20           # au-delà : saut à vérifier (hors fractionnement connu)
MAX_MISSING_SESSION_RATE = 0.01  # 1 % de séances manquantes tolérées
MIN_DAILY_DOLLAR_VOLUME = 1_000_000  # liquidité minimale pour l'éligibilité
EXPECTED_RTH_BARS_5M = 78            # 6h30 de séance régulière / 5 min
MIN_SESSION_BAR_RATIO = 0.50         # séance jugée très amputée en deçà de ce ratio
NEIGHBOURHOOD_FULL_RATIO = 0.90      # voisinage jugé plein au-delà : la séance creuse est alors un trou

# Contrainte de compte
STARTING_CASH_CAD = 200.0
