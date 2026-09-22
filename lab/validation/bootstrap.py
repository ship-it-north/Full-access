"""Bootstrap 95% CI pour l'espérance hors échantillon."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BootstrapCI:
    """Intervalle de confiance bootstrap."""
    mean: float
    ci_lower: float
    ci_upper: float
    std: float
    n_resamples: int
    n_trades: int


def bootstrap_ci(trades: list[float] | np.ndarray,
                 n_resamples: int = 10_000,
                 ci: float = 0.95,
                 seed: int | None = None) -> BootstrapCI:
    """
    Calculer l'IC 95% par rééchantillonnage bootstrap.

    Args:
        trades: liste des trades (PnL en $ CAD)
        n_resamples: nombre de rééchantillonnages
        ci: niveau de confiance (défaut 0.95 = 95%)
        seed: graine aléatoire pour reproductibilité

    Returns:
        BootstrapCI avec moyenne, limites IC, écart-type
    """
    trades = np.array(trades, dtype=float)
    if len(trades) == 0:
        raise ValueError("No trades to bootstrap")

    if seed is not None:
        np.random.seed(seed)

    mean = np.mean(trades)
    std = np.std(trades, ddof=1)

    # Rééchantillonner avec remplacement
    resampled_means = []
    for _ in range(n_resamples):
        sample = np.random.choice(trades, size=len(trades), replace=True)
        resampled_means.append(np.mean(sample))

    resampled_means = np.array(resampled_means)

    # Centiles pour l'IC (par défaut 95% = 2.5% et 97.5%)
    alpha = (1 - ci) / 2
    ci_lower = np.percentile(resampled_means, alpha * 100)
    ci_upper = np.percentile(resampled_means, (1 - alpha) * 100)

    return BootstrapCI(
        mean=mean,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        std=std,
        n_resamples=n_resamples,
        n_trades=len(trades)
    )


def bootstrap_ci_ratio(wins: list[float], losses: list[float],
                       n_resamples: int = 10_000,
                       seed: int | None = None) -> BootstrapCI:
    """
    Bootstrap pour le ratio win/loss ou autre métrique composite.
    """
    wins = np.array(wins, dtype=float)
    losses = np.array(losses, dtype=float)

    if len(wins) + len(losses) == 0:
        raise ValueError("No trades to bootstrap")

    if seed is not None:
        np.random.seed(seed)

    all_trades = np.concatenate([wins, losses])
    mean = np.sum(wins) / np.sum(np.abs(losses)) if np.sum(np.abs(losses)) > 0 else float('inf')

    resampled_ratios = []
    for _ in range(n_resamples):
        sample = np.random.choice(all_trades, size=len(all_trades), replace=True)
        sample_wins = sample[sample > 0]
        sample_losses = sample[sample < 0]
        win_sum = np.sum(sample_wins) if len(sample_wins) > 0 else 0
        loss_sum = np.sum(np.abs(sample_losses)) if len(sample_losses) > 0 else 1e-9
        ratio = win_sum / loss_sum if loss_sum > 0 else float('inf')
        resampled_ratios.append(ratio)

    resampled_ratios = np.array(resampled_ratios)
    resampled_ratios = resampled_ratios[np.isfinite(resampled_ratios)]

    if len(resampled_ratios) == 0:
        return BootstrapCI(mean=mean, ci_lower=0, ci_upper=0, std=0,
                          n_resamples=n_resamples, n_trades=len(all_trades))

    ci_lower = np.percentile(resampled_ratios, 2.5)
    ci_upper = np.percentile(resampled_ratios, 97.5)

    return BootstrapCI(
        mean=mean,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        std=np.std(resampled_ratios, ddof=1),
        n_resamples=n_resamples,
        n_trades=len(all_trades)
    )
