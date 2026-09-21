"""Interface commune aux fournisseurs de données."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ProviderUnavailable(RuntimeError):
    """Le fournisseur ne peut pas servir la requête (pas de clé, pas de connexion).

    Le brief interdit d'inventer des données : on lève, on ne substitue pas
    silencieusement une autre source.
    """


class Provider(ABC):
    name: str = "base"
    adjusted: bool = False

    @abstractmethod
    def fetch(self, symbol: str, timeframe: str, start: str, end: str | None = None) -> pd.DataFrame:
        """OHLCV indexé par date (quotidien) ou par datetime New York (intraday).

        Colonnes attendues : open, high, low, close, adj_close, volume.
        """

    def available(self) -> tuple[bool, str]:
        """(disponible, raison si indisponible)."""
        return True, ""
