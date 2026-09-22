"""Tournament: classement et verdict final par stratégie."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .bootstrap import BootstrapCI
from .monte_carlo import MonteCarloResult
from .walk_forward import WalkForwardReport


class TournamentVerdict(Enum):
    """Résultat du tournoi."""
    PASS = "PASS"
    FAIL_MIN_TRADES = "FAIL_MIN_TRADES"
    FAIL_OUT_OF_SAMPLE = "FAIL_OUT_OF_SAMPLE"
    FAIL_CI_LOWER = "FAIL_CI_LOWER"
    FAIL_PROFIT_FACTOR = "FAIL_PROFIT_FACTOR"
    FAIL_NEIGHBOR_PARAMS = "FAIL_NEIGHBOR_PARAMS"
    FAIL_MONTE_CARLO = "FAIL_MONTE_CARLO"
    FAIL_MARKET_REGIMES = "FAIL_MARKET_REGIMES"
    FAIL_CAPITAL = "FAIL_CAPITAL"


@dataclass(frozen=True)
class TournamentCriteria:
    """Critères de passage stricts."""
    min_total_trades: int = 200  # 100 pour actives, plus pour momentum
    min_out_of_sample_trades: int = 50
    min_ci_lower_pnl_cad: float = 0.0  # IC basse > 0
    min_profit_factor: float = 1.2
    min_neighbors_positive_pct: float = 0.60  # 60% des voisins positifs
    max_monte_carlo_drawdown_50pct: float = 0.05  # < 5%
    min_market_regimes: int = 3
    max_initial_equity: float = float('inf')  # pas de limite par défaut


@dataclass(frozen=True)
class StrategyResult:
    """Résultat complet pour une stratégie."""
    strategy_name: str
    timeframe: str
    verdict: TournamentVerdict
    fail_reason: str | None
    num_total_trades: int | None
    num_out_of_sample_trades: int
    bootstrap_ci: BootstrapCI | None
    profit_factor: float | None
    monte_carlo: MonteCarloResult | None
    required_capital: float | None  # capital minimal si pas PASS


def evaluate_strategy(name: str, timeframe: str,
                      wf_report: WalkForwardReport,
                      bootstrap: BootstrapCI,
                      monte_carlo: MonteCarloResult,
                      criteria: TournamentCriteria = None,
                      initial_equity: float = 200.0) -> StrategyResult:
    """
    Évaluer une stratégie contre les critères du tournoi.
    """
    if criteria is None:
        criteria = TournamentCriteria()

    # Critère 1 : au moins 200 trades totaux (ou 100 pour actives)
    num_trades = wf_report.num_out_of_sample_trades
    min_trades = criteria.min_total_trades if timeframe == "1d" else 100
    if num_trades < min_trades:
        return StrategyResult(
            strategy_name=name,
            timeframe=timeframe,
            verdict=TournamentVerdict.FAIL_MIN_TRADES,
            fail_reason=f"Seulement {num_trades} trades, {min_trades} requis",
            num_total_trades=num_trades,
            num_out_of_sample_trades=num_trades,
            bootstrap_ci=bootstrap,
            profit_factor=wf_report.profit_factor(),
            monte_carlo=monte_carlo,
            required_capital=None
        )

    # Critère 2 : au moins 50 trades hors échantillon
    if num_trades < criteria.min_out_of_sample_trades:
        return StrategyResult(
            strategy_name=name,
            timeframe=timeframe,
            verdict=TournamentVerdict.FAIL_OUT_OF_SAMPLE,
            fail_reason=f"Seulement {num_trades} trades hors échantillon, "
                       f"{criteria.min_out_of_sample_trades} requis",
            num_total_trades=num_trades,
            num_out_of_sample_trades=num_trades,
            bootstrap_ci=bootstrap,
            profit_factor=wf_report.profit_factor(),
            monte_carlo=monte_carlo,
            required_capital=None
        )

    # Critère 3 : IC inférieure > 0 après frais
    if bootstrap.ci_lower <= criteria.min_ci_lower_pnl_cad:
        return StrategyResult(
            strategy_name=name,
            timeframe=timeframe,
            verdict=TournamentVerdict.FAIL_CI_LOWER,
            fail_reason=f"IC 95% basse = {bootstrap.ci_lower:.2f} $ ≤ 0 "
                       f"(moyenne {bootstrap.mean:.2f} $)",
            num_total_trades=num_trades,
            num_out_of_sample_trades=num_trades,
            bootstrap_ci=bootstrap,
            profit_factor=wf_report.profit_factor(),
            monte_carlo=monte_carlo,
            required_capital=None
        )

    # Critère 4 : profit factor > 1.2
    pf = wf_report.profit_factor()
    if pf < criteria.min_profit_factor:
        return StrategyResult(
            strategy_name=name,
            timeframe=timeframe,
            verdict=TournamentVerdict.FAIL_PROFIT_FACTOR,
            fail_reason=f"Profit factor = {pf:.2f}, {criteria.min_profit_factor} requis",
            num_total_trades=num_trades,
            num_out_of_sample_trades=num_trades,
            bootstrap_ci=bootstrap,
            profit_factor=pf,
            monte_carlo=monte_carlo,
            required_capital=None
        )

    # Critère 5 : Monte Carlo drawdown 50% < 5%
    if monte_carlo.prob_drawdown_50pct > criteria.max_monte_carlo_drawdown_50pct:
        return StrategyResult(
            strategy_name=name,
            timeframe=timeframe,
            verdict=TournamentVerdict.FAIL_MONTE_CARLO,
            fail_reason=f"Proba drawdown 50% = {monte_carlo.prob_drawdown_50pct:.1%} "
                       f"> {criteria.max_monte_carlo_drawdown_50pct:.1%}",
            num_total_trades=num_trades,
            num_out_of_sample_trades=num_trades,
            bootstrap_ci=bootstrap,
            profit_factor=pf,
            monte_carlo=monte_carlo,
            required_capital=None
        )

    # Tous les critères sont passés
    return StrategyResult(
        strategy_name=name,
        timeframe=timeframe,
        verdict=TournamentVerdict.PASS,
        fail_reason=None,
        num_total_trades=num_trades,
        num_out_of_sample_trades=num_trades,
        bootstrap_ci=bootstrap,
        profit_factor=pf,
        monte_carlo=monte_carlo,
        required_capital=None
    )


@dataclass(frozen=True)
class TournamentReport:
    """Rapport du tournoi : classement et verdicts."""
    results: list[StrategyResult]
    passing_strategies: list[str]
    failing_strategies: dict[str, str]  # nom -> raison du failure

    @property
    def num_passing(self) -> int:
        return len(self.passing_strategies)

    @property
    def num_failing(self) -> int:
        return len(self.failing_strategies)
