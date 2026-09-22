"""Tests pour la validation (walk-forward, bootstrap, Monte Carlo)."""

import numpy as np
import pandas as pd
import pytest

from lab.validation.bootstrap import bootstrap_ci, bootstrap_ci_ratio
from lab.validation.monte_carlo import monte_carlo_permutations
from lab.validation.tournament import evaluate_strategy, TournamentVerdict
from lab.validation.walk_forward import walk_forward_split, WalkForwardWindow
from lab.backtest.engine import _is_market_hours


class TestWalkForward:
    """Tests pour la division walk-forward."""

    def test_basic_split(self):
        """Créer une fenêtre walk-forward simple."""
        dates = pd.date_range("2020-01-01", periods=3 * 365, freq="D")
        windows = walk_forward_split(dates, train_months=12, test_months=3, step_months=3)

        assert len(windows) > 0
        # Vérifier que train et test ne se chevauchent pas
        for w in windows:
            assert w.train_end < w.test_start

    def test_no_overlap_train_test(self):
        """Les fenêtres train et test ne se chevauchent pas."""
        dates = pd.date_range("2015-01-01", periods=10 * 365, freq="D")
        windows = walk_forward_split(dates)

        for w in windows:
            assert w.train_end < w.test_start


class TestBootstrap:
    """Tests pour le bootstrap."""

    def test_bootstrap_positive_trades(self):
        """Bootstrap sur des trades positifs."""
        trades = [1.0, 2.0, 1.5, 2.5, 1.2]
        result = bootstrap_ci(trades, n_resamples=1000, seed=42)

        assert result.mean == pytest.approx(np.mean(trades))
        assert result.ci_lower < result.mean < result.ci_upper
        assert result.n_trades == len(trades)

    def test_bootstrap_mixed_trades(self):
        """Bootstrap avec des trades positifs et négatifs."""
        trades = [10.0, -5.0, 8.0, -2.0, 12.0]
        result = bootstrap_ci(trades, n_resamples=1000, seed=42)

        assert result.ci_lower <= result.mean <= result.ci_upper
        # Moyenne devrait être positive
        assert result.mean == pytest.approx(np.mean(trades))

    def test_bootstrap_ci_bounds(self):
        """IC 95% devrait contenir la vraie moyenne avec haute probabilité."""
        np.random.seed(42)
        trades = np.random.normal(loc=5.0, scale=2.0, size=100)
        result = bootstrap_ci(list(trades), n_resamples=5000, seed=42)

        assert result.ci_lower < result.mean < result.ci_upper
        assert result.n_trades == 100


class TestMonteCarlo:
    """Tests pour Monte Carlo."""

    def test_monte_carlo_simple(self):
        """MC sur une série simple de trades."""
        trades = [1.0, 2.0, -0.5, 1.5, -1.0]
        result = monte_carlo_permutations(trades, initial_equity=10.0, n_simulations=100, seed=42)

        assert result.n_simulations == 100
        assert 0 <= result.prob_drawdown_25pct <= 1
        assert 0 <= result.prob_drawdown_50pct <= 1

    def test_monte_carlo_winning_trades(self):
        """MC sur des trades gagnants → probabilité positive élevée."""
        trades = [20.0, 30.0, 15.0, 25.0]  # tous positifs, somme 90
        result = monte_carlo_permutations(trades, initial_equity=200.0, n_simulations=100, seed=42)

        # Avec que des trades positifs, final equity = initial + sum
        expected_final = 200.0 + sum(trades)  # 200 + 90 = 290
        assert result.final_equity_mean == pytest.approx(expected_final, rel=0.01)

    def test_monte_carlo_losing_trades(self):
        """MC sur des trades perdants → drawdown élevé."""
        trades = [-50.0, -30.0, -20.0]  # tous négatifs, perte totale 100
        result = monte_carlo_permutations(trades, initial_equity=100.0, n_simulations=100, seed=42)

        # Perte importante attendue
        assert result.final_equity_mean == 0.0  # 100 - 100 = 0
        assert result.prob_drawdown_50pct > 0.5  # probable de perdre 50%


class TestTournament:
    """Tests pour le système de tournoi."""

    def test_criterion_min_trades(self):
        """Vérifier le critère du nombre minimum de trades."""
        from lab.validation.walk_forward import WalkForwardReport
        from lab.validation.bootstrap import BootstrapCI
        from lab.validation.monte_carlo import MonteCarloResult

        # Créer un rapport avec trop peu de trades
        trades = [1.0, -0.5]  # 2 trades, besoin de 200
        wf = WalkForwardReport(
            strategy_name="test",
            results=[],
            out_of_sample_trades=[
                {"pnl_cad": t} for t in trades
            ]
        )
        bc = BootstrapCI(mean=0.25, ci_lower=-1, ci_upper=2, std=1, n_resamples=1000, n_trades=2)
        mc = MonteCarloResult(
            n_simulations=100,
            prob_drawdown_25pct=0.5,
            prob_drawdown_50pct=0.2,
            prob_positive_50_trades=np.nan,
            prob_positive_100_trades=np.nan,
            prob_positive_200_trades=np.nan,
            final_equity_mean=200.25,
            final_equity_ci_lower=195,
            final_equity_ci_upper=205,
            max_drawdown_mean=5,
            max_drawdown_ci_lower=2,
            max_drawdown_ci_upper=10
        )

        result = evaluate_strategy("test", "1d", wf, bc, mc)
        assert result.verdict == TournamentVerdict.FAIL_MIN_TRADES

    def test_criterion_ci_lower(self):
        """Vérifier le critère IC basse > 0."""
        from lab.validation.walk_forward import WalkForwardReport
        from lab.validation.bootstrap import BootstrapCI
        from lab.validation.monte_carlo import MonteCarloResult

        # 200+ trades mais IC basse négative
        trades = [1.0] * 150 + [-0.5] * 50  # 200 trades, 150 positifs
        wf = WalkForwardReport(
            strategy_name="test",
            results=[],
            out_of_sample_trades=[{"pnl_cad": t} for t in trades]
        )
        bc = BootstrapCI(mean=1.0, ci_lower=-0.5, ci_upper=2.5, std=1, n_resamples=1000, n_trades=200)
        mc = MonteCarloResult(
            n_simulations=100, prob_drawdown_25pct=0.1, prob_drawdown_50pct=0.01,
            prob_positive_50_trades=0.9, prob_positive_100_trades=0.8, prob_positive_200_trades=0.7,
            final_equity_mean=260, final_equity_ci_lower=240, final_equity_ci_upper=280,
            max_drawdown_mean=5, max_drawdown_ci_lower=2, max_drawdown_ci_upper=10
        )

        result = evaluate_strategy("test", "1d", wf, bc, mc)
        assert result.verdict == TournamentVerdict.FAIL_CI_LOWER

    def test_pass_all_criteria(self):
        """Stratégie qui passe tous les critères."""
        from lab.validation.walk_forward import WalkForwardReport
        from lab.validation.bootstrap import BootstrapCI
        from lab.validation.monte_carlo import MonteCarloResult

        trades = [1.5, 2.0, 1.2] * 70  # 210 trades positifs
        wf = WalkForwardReport(
            strategy_name="test",
            results=[],
            out_of_sample_trades=[{"pnl_cad": t} for t in trades]
        )
        bc = BootstrapCI(mean=1.567, ci_lower=1.2, ci_upper=1.9, std=0.5, n_resamples=1000, n_trades=210)
        mc = MonteCarloResult(
            n_simulations=100, prob_drawdown_25pct=0.01, prob_drawdown_50pct=0.0,
            prob_positive_50_trades=0.99, prob_positive_100_trades=0.99, prob_positive_200_trades=0.95,
            final_equity_mean=530, final_equity_ci_lower=510, final_equity_ci_upper=550,
            max_drawdown_mean=2, max_drawdown_ci_lower=0.5, max_drawdown_ci_upper=5
        )

        result = evaluate_strategy("test", "1d", wf, bc, mc)
        assert result.verdict == TournamentVerdict.PASS


class TestMarketHours:
    """Tests pour le filtrage des heures de marché."""

    def test_rejects_pre_market_5min(self):
        """Rejette les barres avant 9:30 ET pour intraday."""
        ts = pd.Timestamp("2023-06-15 09:25:00", tz="America/New_York")
        assert not _is_market_hours(ts, "5m")

    def test_accepts_market_hours_5min(self):
        """Accepte les barres entre 9:30 et 16:00 ET pour intraday."""
        ts = pd.Timestamp("2023-06-15 10:00:00", tz="America/New_York")
        assert _is_market_hours(ts, "5m")

    def test_rejects_post_market_5min(self):
        """Rejette les barres après 16:00 ET pour intraday."""
        ts = pd.Timestamp("2023-06-15 16:05:00", tz="America/New_York")
        assert not _is_market_hours(ts, "5m")

    def test_accepts_market_close_5min(self):
        """Accepte la barre de 16:00 ET pour intraday."""
        ts = pd.Timestamp("2023-06-15 16:00:00", tz="America/New_York")
        assert _is_market_hours(ts, "5m")

    def test_rejects_pre_market_daily(self):
        """Rejette les barres quotidiennes avant 16:00 ET."""
        ts = pd.Timestamp("2023-06-15 15:59:00", tz="America/New_York")
        assert not _is_market_hours(ts, "1d")

    def test_accepts_market_close_daily(self):
        """Accepte les barres quotidiennes à/après 16:00 ET."""
        ts = pd.Timestamp("2023-06-15 16:00:00", tz="America/New_York")
        assert _is_market_hours(ts, "1d")

    def test_handles_utc_timestamps(self):
        """Convertit correctement les timestamps UTC."""
        # 14:00 UTC = 10:00 ET (EDT)
        ts = pd.Timestamp("2023-06-15 14:00:00", tz="UTC")
        assert _is_market_hours(ts, "5m")

        # 20:05 UTC = 16:05 ET (EDT) - après marché
        ts = pd.Timestamp("2023-06-15 20:05:00", tz="UTC")
        assert not _is_market_hours(ts, "5m")
