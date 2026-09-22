"""Walk-forward validation: optimize on one window, test on the next."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WalkForwardWindow:
    """Un fenêtre d'optimisation + validation."""
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def walk_forward_split(data_index: pd.DatetimeIndex,
                       train_months: int = 12,
                       test_months: int = 3,
                       step_months: int = 3) -> list[WalkForwardWindow]:
    """
    Créer des fenêtres walk-forward : optimiser sur train_months,
    tester sur test_months, avancer de step_months.

    Args:
        data_index: index temporel complet
        train_months: taille fenêtre apprentissage
        test_months: taille fenêtre test (hors échantillon)
        step_months: avancer de combien de mois

    Returns:
        liste des fenêtres walk-forward
    """
    if len(data_index) == 0:
        return []

    # Ensure DatetimeIndex
    if not isinstance(data_index, pd.DatetimeIndex):
        data_index = pd.DatetimeIndex(data_index)

    # Preserve timezone info
    original_tz = data_index.tz

    # Convert to tz-naive for period conversion
    if original_tz is not None:
        data_index_naive = data_index.tz_localize(None)
    else:
        data_index_naive = data_index

    start = data_index_naive[0].to_period("M")
    end = data_index_naive[-1].to_period("M")

    windows = []
    train_start = start

    while train_start < end:
        train_end_period = train_start + train_months - 1
        test_start_period = train_end_period + 1
        test_end_period = test_start_period + test_months - 1

        if test_end_period >= end:
            break

        # Convert periods to timestamps
        train_start_ts = train_start.start_time
        train_end_ts = train_end_period.end_time

        test_start_ts = test_start_period.start_time
        test_end_ts = test_end_period.end_time

        # Reattach timezone if needed
        if original_tz is not None:
            train_start_ts = train_start_ts.tz_localize(original_tz)
            train_end_ts = train_end_ts.tz_localize(original_tz)
            test_start_ts = test_start_ts.tz_localize(original_tz)
            test_end_ts = test_end_ts.tz_localize(original_tz)

        # Limit to available data
        train_start_ts = max(train_start_ts, data_index[0])
        train_end_ts = min(train_end_ts, data_index[-1])
        test_start_ts = max(test_start_ts, data_index[0])
        test_end_ts = min(test_end_ts, data_index[-1])

        if train_start_ts < train_end_ts and test_start_ts < test_end_ts:
            windows.append(WalkForwardWindow(
                train_start=train_start_ts,
                train_end=train_end_ts,
                test_start=test_start_ts,
                test_end=test_end_ts,
            ))

        train_start = train_start + step_months

    return windows


def split_by_window(data: pd.DataFrame,
                    window: WalkForwardWindow) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Diviser data selon fenêtre : retourner (train, test)."""
    train = data[(data.index >= window.train_start) & (data.index <= window.train_end)]
    test = data[(data.index >= window.test_start) & (data.index <= window.test_end)]
    return train, test


@dataclass(frozen=True)
class OptimizationResult:
    """Résultat d'optimisation sur une fenêtre."""
    window: WalkForwardWindow
    best_params: dict
    best_in_sample_metric: float  # ex: Sharpe, profit factor
    test_results: dict  # résultats hors échantillon sur cette fenêtre


@dataclass(frozen=True)
class WalkForwardReport:
    """Rapport complet walk-forward : tous les résultats."""
    strategy_name: str
    results: list[OptimizationResult]
    out_of_sample_trades: list[dict]  # agrégation de tous les trades test

    @property
    def out_of_sample_pnl(self) -> float:
        """PnL total hors échantillon en $ CAD."""
        return sum(t.get("pnl_cad", 0) for t in self.out_of_sample_trades)

    @property
    def num_out_of_sample_trades(self) -> int:
        return len(self.out_of_sample_trades)

    def profit_factor(self) -> float:
        """Ratio wins / losses hors échantillon."""
        wins = sum(t.get("pnl_cad", 0) for t in self.out_of_sample_trades
                  if t.get("pnl_cad", 0) > 0)
        losses = abs(sum(t.get("pnl_cad", 0) for t in self.out_of_sample_trades
                        if t.get("pnl_cad", 0) < 0))
        if losses == 0:
            return float('inf') if wins > 0 else 1.0
        return wins / losses
