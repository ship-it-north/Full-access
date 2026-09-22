"""Monte Carlo simulation: drawdown, ruin probability, equity distribution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MonteCarloResult:
    """Résultats Monte Carlo sur 10k permutations."""
    n_simulations: int
    prob_drawdown_25pct: float
    prob_drawdown_50pct: float
    prob_positive_50_trades: float
    prob_positive_100_trades: float
    prob_positive_200_trades: float
    final_equity_mean: float
    final_equity_ci_lower: float
    final_equity_ci_upper: float
    max_drawdown_mean: float
    max_drawdown_ci_lower: float
    max_drawdown_ci_upper: float


def monte_carlo_permutations(trades: list[float] | np.ndarray,
                             initial_equity: float = 200.0,
                             n_simulations: int = 10_000,
                             seed: int | None = None) -> MonteCarloResult:
    """
    Permuter l'ordre des trades N fois et mesurer la distribution des résultats.

    Args:
        trades: liste des PnL (en $ CAD)
        initial_equity: capital de départ
        n_simulations: nombre de permutations
        seed: graine aléatoire

    Returns:
        MonteCarloResult avec probabilités et distributions
    """
    trades = np.array(trades, dtype=float)
    if len(trades) == 0:
        raise ValueError("No trades for Monte Carlo")

    if seed is not None:
        np.random.seed(seed)

    final_equities = []
    max_drawdowns = []
    trades_to_50 = []
    trades_to_100 = []
    trades_to_200 = []

    for _ in range(n_simulations):
        # Permuter l'ordre des trades
        perm = np.random.permutation(trades)

        # Simuler l'équité: initial + cumulative trades
        equity_path = np.insert(initial_equity + np.cumsum(perm), 0, initial_equity)

        # Équité finale
        final_equities.append(equity_path[-1])

        # Drawdown maximal
        running_max = np.maximum.accumulate(equity_path)
        drawdown = (equity_path - running_max) / running_max
        max_drawdowns.append(np.abs(drawdown.min()) * 100)  # en %

        # Probabilité d'être positif après N trades (relative à initial_equity)
        cumsum = initial_equity + np.cumsum(perm)
        if len(cumsum) >= 50:
            trades_to_50.append(cumsum[49] > initial_equity)
        if len(cumsum) >= 100:
            trades_to_100.append(cumsum[99] > initial_equity)
        if len(cumsum) >= 200:
            trades_to_200.append(cumsum[199] > initial_equity)

    final_equities = np.array(final_equities)
    max_drawdowns = np.array(max_drawdowns)

    # Probabilités de drawdown
    prob_dd_25 = np.mean(max_drawdowns > 25)
    prob_dd_50 = np.mean(max_drawdowns > 50)

    # Probabilités positives après N trades
    prob_pos_50 = np.mean(trades_to_50) if trades_to_50 else np.nan
    prob_pos_100 = np.mean(trades_to_100) if trades_to_100 else np.nan
    prob_pos_200 = np.mean(trades_to_200) if trades_to_200 else np.nan

    return MonteCarloResult(
        n_simulations=n_simulations,
        prob_drawdown_25pct=prob_dd_25,
        prob_drawdown_50pct=prob_dd_50,
        prob_positive_50_trades=prob_pos_50,
        prob_positive_100_trades=prob_pos_100,
        prob_positive_200_trades=prob_pos_200,
        final_equity_mean=np.mean(final_equities),
        final_equity_ci_lower=np.percentile(final_equities, 2.5),
        final_equity_ci_upper=np.percentile(final_equities, 97.5),
        max_drawdown_mean=np.mean(max_drawdowns),
        max_drawdown_ci_lower=np.percentile(max_drawdowns, 2.5),
        max_drawdown_ci_upper=np.percentile(max_drawdowns, 97.5),
    )


def monte_carlo_bootstrap_final_equity(trades: list[float] | np.ndarray,
                                      initial_equity: float = 200.0,
                                      n_simulations: int = 10_000,
                                      seed: int | None = None) -> tuple[float, float, float]:
    """
    Variante : resample avec remplacement au lieu de permutation.

    Returns:
        (mean, ci_lower, ci_upper) de l'équité finale
    """
    trades = np.array(trades, dtype=float)
    if len(trades) == 0:
        raise ValueError("No trades")

    if seed is not None:
        np.random.seed(seed)

    final_equities = []
    for _ in range(n_simulations):
        sample = np.random.choice(trades, size=len(trades), replace=True)
        final_eq = initial_equity + np.sum(sample)
        final_equities.append(final_eq)

    final_equities = np.array(final_equities)
    return (np.mean(final_equities),
            np.percentile(final_equities, 2.5),
            np.percentile(final_equities, 97.5))
