"""Moteur de backtest : orchestration complète."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from lab.core.broker_sim import entry_fill, exit_fill, time_exit_fill, Fill
from lab.core.costs import commission, convert, to_cad
from lab.core.portfolio import Portfolio, settlement_date
from lab.core.risk import RiskState, size_position, Sizing
from lab.strategies.base import Context, ExitRule, OrderType, Signal, Strategy


@dataclass(frozen=True)
class Trade:
    """Un trade complètement exécuté (entrée + sortie)."""
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    entry_reason: str
    shares: float
    stop: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str
    pnl_local: float  # en devise locale
    pnl_cad: float
    risk_cad: float
    commission_round_trip: float
    risk_used: float  # % du plafond 5$ utilisé


@dataclass
class BacktestContext:
    """État du backtest à chaque pas de temps."""
    current_date: pd.Timestamp
    bar: pd.DataFrame  # historique jusquà current_date pour le symbole actuel
    portfolio: Portfolio
    risk_state: RiskState
    usd_per_cad: float
    fx_converted: bool = False
    initial_cash: float = 200.0  # CAD


@dataclass
class BacktestResult:
    """Résultats d'un backtest."""
    strategy_name: str
    timeframe: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    trades: list[Trade] = field(default_factory=list)
    final_equity_cad: float = 0.0
    total_pnl_cad: float = 0.0
    num_trades: int = 0
    num_winning: int = 0
    num_losing: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_drawdown_pct: float = 0.0


class BacktestEngine:
    """Moteur de backtest pour une stratégie donnée."""

    def __init__(self, strategy: Strategy,
                 data: dict[str, pd.DataFrame],
                 usd_per_cad: float = 1.35,
                 initial_equity_cad: float = 200.0,
                 commission_profile: str = "tiered",
                 fractional: bool = False):
        """
        Args:
            strategy: instance Strategy
            data: dict symbol -> DataFrame (OHLCV)
            usd_per_cad: taux de change
            initial_equity_cad: capital initial en CAD
            commission_profile: "tiered" ou "fixed"
            fractional: actions fractionnées disponibles
        """
        self.strategy = strategy
        self.data = data
        self.usd_per_cad = usd_per_cad
        self.initial_equity_cad = initial_equity_cad
        self.commission_profile = commission_profile
        self.fractional = fractional

    def run(self) -> BacktestResult:
        """Exécuter le backtest complet."""
        result = BacktestResult(
            strategy_name=self.strategy.__class__.__name__,
            timeframe=self.strategy.timeframe,
            start_date=None,
            end_date=None,
        )

        if not self.data:
            return result

        # Convertir CAD en USD une seule fois
        fx_conv = convert(self.initial_equity_cad, self.usd_per_cad)
        cash_usd = fx_conv.amount_target
        portfolio = Portfolio(
            cash_settled=cash_usd,
            usd_per_cad=self.usd_per_cad,
            currency="USD"
        )
        risk_state = RiskState()

        # Déterminer les dates globales
        all_dates = set()
        for df in self.data.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        if not all_dates:
            return result

        result.start_date = all_dates[0]
        result.end_date = all_dates[-1]

        # Traiter chaque date
        for date in all_dates:
            # Libérer les produits de vente réglés
            portfolio.release_settled(date)

            # Parcourir les symboles de l'univers
            for symbol in self.data:
                df = self.data[symbol]
                if date not in df.index:
                    continue

                # Construire l'historique jusqu'à cette date
                history = df[:date]
                if len(history) == 0:
                    continue

                # Vérifier éligibilité
                if not self.strategy.universe_filter(symbol, history):
                    continue

                # Créer le contexte
                ctx = Context(
                    symbol=symbol,
                    timeframe=self.strategy.timeframe,
                    bar=history.iloc[-1],
                    history=history,
                    usd_per_cad=self.usd_per_cad,
                    fractional=self.fractional,
                )

                # Demander un signal
                signal = self.strategy.on_bar_close(ctx)
                if signal is None:
                    continue

                # Traiter le signal (entrée au marché)
                # [À simplifier pour Phase D initial : pas de gestion des positions ouvertes]
                # [Cette version juste enregistre les signaux]

        # Calculer les métriques finales
        result.trades = []  # À implémenter quand moteur d'exécution complet
        result.final_equity_cad = portfolio.equity_cad()
        result.total_pnl_cad = result.final_equity_cad - self.initial_equity_cad
        result.num_trades = len(result.trades)

        return result
