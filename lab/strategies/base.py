"""Stratégies multi-délais : interface et contexte commun."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class ExitRule(Enum):
    """Type de sortie : cible en R, stop suiveur, temporelle, ou signal."""
    TARGET = "target"
    TRAILING_STOP = "trailing_stop"
    TIME_BASED = "time_based"
    SIGNAL = "signal"


class OrderType(Enum):
    """Type d'ordre d'entrée."""
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class Signal:
    """Signal d'entrée produit par une stratégie."""
    symbol: str
    order_type: OrderType
    limit_price: float | None
    stop: float
    exit_rule: ExitRule
    exit_param: float | int | None  # R multiplier, ATR factor, days, etc.
    expiration_bars: int  # nombre de barres avant expiration du signal
    reason: str  # explication pour Telegram


@dataclass
class Context:
    """Contexte de barre partagé entre le moteur et les stratégies."""
    symbol: str
    timeframe: str  # "1d" ou "5m"
    bar: pd.Series  # OHLCV + indicateurs pour cette barre
    history: pd.DataFrame  # historique complet jusqu'à cette barre
    events: pd.DatetimeIndex | None = None  # événements macro (FOMC, CPI, jobs)
    usd_per_cad: float = 1.35
    fractional: bool = False  # actions fractionnées disponibles?


class Strategy(ABC):
    """Interface commune à toutes les stratégies."""

    @property
    @abstractmethod
    def timeframe(self) -> str:
        """'1d' ou '5m'."""
        pass

    @abstractmethod
    def universe_filter(self, symbol: str, data: pd.DataFrame) -> bool:
        """Indique si le symbole est éligible (suffisamment liquide, prix acceptable)."""
        pass

    @abstractmethod
    def on_bar_close(self, ctx: Context) -> Signal | None:
        """
        À chaque fermeture de barre, retourne un signal d'entrée ou None.
        Ne doit jamais regarder des données futures.
        """
        pass

    @abstractmethod
    def params_grid(self) -> list[dict]:
        """
        Retourne la grille de sensibilité (environ 20 combinaisons max).
        Chaque dict contient les paramètres d'une combinaison.
        """
        pass
