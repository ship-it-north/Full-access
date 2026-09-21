"""Paramètres du backtester swing crypto.

Toutes les valeurs numériques des règles, des frictions et du risk management
sont centralisées ici. Aucun autre module ne doit contenir de constante métier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"

# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #
EXCHANGE_ID = "bybit"
MARKET_TYPE = "swap"
QUOTE = "USDT"
TIMEFRAME = "1h"
BAR_MS = 60 * 60 * 1000
START_DATE = "2023-01-01T00:00:00Z"
UNIVERSE_SIZE = 30
OHLCV_LIMIT = 1000  # max de bougies par appel Bybit
RATE_LIMIT_SLEEP = 0.05  # marge au-dessus du rate limit ccxt
MAX_RETRIES = 5

# Exclus de l'univers : stablecoins et tokens à levier.
STABLE_BASES = {
    "USDT", "USDC", "USDE", "DAI", "TUSD", "BUSD", "FDUSD", "USDD", "PYUSD",
    "USDP", "GUSD", "LUSD", "SUSD", "USDS", "USD1", "RLUSD", "EURT", "EURS",
    "USDY", "USDX", "FRAX", "MIM", "USTC",
}
LEVERAGED_PATTERNS = ("3L", "3S", "5L", "5S", "2L", "2S", "UP", "DOWN", "BULL", "BEAR")
# Actifs tokenisés non-crypto cotés en perp sur certains exchanges (or, pétrole,
# actions) : hors univers crypto.
NON_CRYPTO_BASES = {
    "XAU", "XAG", "XPT", "XPD", "CL", "BZ", "NG", "SPX", "NDX", "DJI",
    "SNDK", "TSLA", "NVDA", "AAPL", "MSTR", "COIN", "META", "AMZN", "GOOGL",
    "SOXL", "SOXS", "TQQQ", "SQQQ", "RIVER", "CRCL", "HOOD", "PLTR", "GOOG", "SKHYNIX",
}

# --------------------------------------------------------------------------- #
# Règles de la stratégie
# --------------------------------------------------------------------------- #
TREND_LOOKBACK = 720          # barres pour la variation de tendance
TREND_MIN_CHANGE = 0.30       # +30%
TREND_MAX_CHANGE = 1.00       # +100%
SMA_PERIOD = 200

PIVOT_LEFT = 5
PIVOT_RIGHT = 5
PIVOT_CONFIRM_LAG = 5         # un pivot n'est exploitable qu'à pivot_index + lag

NEW_HIGH_LOOKBACK = 200       # le max des 200 dernières barres...
NEW_HIGH_MAX_AGE = 30         # ...doit dater de moins de 30 barres

SUPPORT_LOOKBACK = 500        # pivots bas considérés pour le clustering
CLUSTER_TOLERANCE = 0.010     # 1.0% : même cluster si écart relatif < 1%
MIN_TOUCHES = 2               # niveau "fort"

MAX_L2_DISTANCE = 0.15        # L2 doit être à moins de 15% sous L1
MAX_STOP_DISTANCE = 0.08      # (entrée - stop) / entrée <= 8%
STOP_BUFFER = 0.997           # stop = L2 * 0.997
MIN_RR = 1.5

BREAKOUT_CONFIRM_BARS = 3     # variante B : clôture haussière > L1 dans les 3 barres
TIME_STOP_BARS = 120
# Non spécifié dans les règles : durée de vie d'un ordre en attente non exécuté.
# Nécessaire car une touche de L1 fait passer le prix sous L1, ce qui invalide
# temporairement le setup ; sans cette fenêtre la variante B ne pourrait jamais
# se déclencher. L'ordre est annulé si le filtre de tendance casse ou à expiration.
PENDING_EXPIRY_BARS = 30

# --------------------------------------------------------------------------- #
# Frictions (obligatoires)
# --------------------------------------------------------------------------- #
MAKER_FEE = 0.0002            # 0.02%
TAKER_FEE = 0.00055           # 0.055%
FUNDING_RATE_8H = 0.0001      # 0.01% par 8h de détention
STOP_SLIPPAGE = 0.0005        # 0.05% sur les sorties au stop
FUNDING_INTERVAL_BARS = 8     # 8 barres 1h = 8h

# --------------------------------------------------------------------------- #
# Risk management
# --------------------------------------------------------------------------- #
INITIAL_CAPITAL = 100.0
RISK_LEVELS = (0.02, 0.05, 0.10)
ENTRY_VARIANTS = ("A", "B")
MAX_CONCURRENT_POSITIONS = 5
# Non spécifié dans les règles : garde-fou pour éviter des notionnels absurdes
# quand la distance au stop est minuscule. Le nombre de trades bridés est reporté.
MAX_LEVERAGE = 10.0

# --------------------------------------------------------------------------- #
# Split in-sample / out-of-sample
# --------------------------------------------------------------------------- #
IS_START = "2023-01-01"
IS_END = "2024-12-31"
OOS_START = "2025-01-01"
OOS_END = "2026-12-31"


@dataclass(frozen=True)
class StrategyConfig:
    """Configuration d'un run. Permet de surcharger les constantes en test."""

    entry_variant: str = "A"
    risk_per_trade: float = 0.02
    initial_capital: float = INITIAL_CAPITAL
    max_concurrent: int = MAX_CONCURRENT_POSITIONS

    trend_lookback: int = TREND_LOOKBACK
    trend_min_change: float = TREND_MIN_CHANGE
    trend_max_change: float = TREND_MAX_CHANGE
    sma_period: int = SMA_PERIOD

    pivot_left: int = PIVOT_LEFT
    pivot_right: int = PIVOT_RIGHT
    pivot_confirm_lag: int = PIVOT_CONFIRM_LAG

    new_high_lookback: int = NEW_HIGH_LOOKBACK
    new_high_max_age: int = NEW_HIGH_MAX_AGE

    support_lookback: int = SUPPORT_LOOKBACK
    cluster_tolerance: float = CLUSTER_TOLERANCE
    min_touches: int = MIN_TOUCHES

    max_l2_distance: float = MAX_L2_DISTANCE
    max_stop_distance: float = MAX_STOP_DISTANCE
    stop_buffer: float = STOP_BUFFER
    min_rr: float = MIN_RR

    breakout_confirm_bars: int = BREAKOUT_CONFIRM_BARS
    time_stop_bars: int = TIME_STOP_BARS
    pending_expiry_bars: int = PENDING_EXPIRY_BARS

    maker_fee: float = MAKER_FEE
    taker_fee: float = TAKER_FEE
    funding_rate_8h: float = FUNDING_RATE_8H
    stop_slippage: float = STOP_SLIPPAGE
    funding_interval_bars: int = FUNDING_INTERVAL_BARS

    tags: tuple = field(default_factory=tuple)

    @property
    def label(self) -> str:
        return f"{self.entry_variant}-risk{self.risk_per_trade:.0%}"
