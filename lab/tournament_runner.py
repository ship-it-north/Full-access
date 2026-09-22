"""Tournament runner: execute all strategies and generate Phase D report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from lab.backtest.engine import BacktestEngine
from lab.strategies.momentum_monthly import MomentumMonthly
from lab.strategies.orb_intraday import ORBIntraday
from lab.strategies.rsi2_reversion import RSI2Reversion
from lab.strategies.swing_pullback import SwingPullback
from lab.strategies.base import Strategy
from lab.validation.bootstrap import bootstrap_ci
from lab.validation.monte_carlo import monte_carlo_permutations
from lab.validation.tournament import evaluate_strategy, TournamentVerdict
from lab.validation.walk_forward import walk_forward_split


class TournamentRunner:
    """Runner pour le tournoi complet des 4 stratégies."""

    def __init__(
        self,
        data_dir: Path | str = "lab/data/cache",
        initial_equity_cad: float = 200.0,
        usd_per_cad: float = 1.35,
    ):
        self.data_dir = Path(data_dir)
        self.initial_equity_cad = initial_equity_cad
        self.usd_per_cad = usd_per_cad

    def load_data(self, symbols: list[str], timeframe: str = "1d") -> dict[str, pd.DataFrame]:
        """Charger les données en cache pour les symboles."""
        data = {}
        timeframe_file = f"{timeframe}.parquet"

        for symbol in symbols:
            cache_path = self.data_dir / symbol
            data_file = cache_path / timeframe_file

            if data_file.exists():
                df = pd.read_parquet(data_file)
                if not df.index.tz:
                    df.index = df.index.tz_localize("UTC")
                data[symbol] = df

        return data

    def run_strategy(
        self,
        strategy: Strategy,
        data: dict[str, pd.DataFrame],
        train_months: int = 12,
        test_months: int = 3,
        step_months: int = 3,
    ) -> dict[str, Any]:
        """Exécuter une stratégie en walk-forward et retourner les résultats."""
        # Déterminer les dates globales
        all_dates = pd.DatetimeIndex([])
        for df in data.values():
            all_dates = all_dates.union(df.index)

        if len(all_dates) == 0:
            return {"trades": [], "error": "No data"}

        # Créer les fenêtres walk-forward
        windows = walk_forward_split(
            all_dates,
            train_months=train_months,
            test_months=test_months,
            step_months=step_months,
        )

        if not windows:
            return {"trades": [], "error": "No walk-forward windows"}

        out_of_sample_trades = []

        for window in windows:
            # Filtrer les données pour la fenêtre de test
            test_data = {}

            for symbol, df in data.items():
                test_df = df[
                    (df.index >= window.test_start) & (df.index <= window.test_end)
                ]

                if len(test_df) > 0:
                    test_data[symbol] = test_df

            if not test_data:
                continue

            # Exécuter le backtest
            engine = BacktestEngine(
                strategy,
                test_data,
                usd_per_cad=self.usd_per_cad,
                initial_equity_cad=self.initial_equity_cad,
            )

            result = engine.run()

            # Collecter les trades
            for trade in result.trades:
                out_of_sample_trades.append({
                    "symbol": trade.symbol,
                    "entry_date": trade.entry_date.isoformat(),
                    "exit_date": trade.exit_date.isoformat(),
                    "pnl_cad": trade.pnl_cad,
                    "risk_cad": trade.risk_cad,
                })

        return {"trades": out_of_sample_trades}

    def run_tournament(self) -> dict[str, Any]:
        """Exécuter le tournoi complet et retourner les résultats."""
        symbols = [
            "SPY", "QQQ", "IWM", "DIA", "BIL", "SGOV",
            "GLD", "TLT", "EFA", "XLE", "XLF", "XLK", "XLV", "XLI",
        ]

        daily_data = self.load_data(symbols, timeframe="1d")
        intraday_data = self.load_data(symbols, timeframe="5m")

        if not daily_data and not intraday_data:
            return {"error": "No data loaded"}

        # Stratégies à tester avec configuration walk-forward
        strategies = [
            ("SwingPullback", SwingPullback(), daily_data, 12, 3, 3),
            ("RSI2Reversion", RSI2Reversion(), daily_data, 12, 3, 3),
            ("MomentumMonthly", MomentumMonthly(), daily_data, 36, 6, 6),
            ("ORBIntraday", ORBIntraday(), intraday_data, 12, 3, 3),
        ]

        tournament_results = []

        for name, strategy, data, train, test, step in strategies:
            if not data:
                tournament_results.append({
                    "strategy": name,
                    "verdict": "SKIP",
                    "reason": "No data available",
                })
                continue

            print(f"\n=== {name} ===")

            # Exécuter la stratégie
            result = self.run_strategy(strategy, data, train, test, step)

            if "error" in result or not result["trades"]:
                tournament_results.append({
                    "strategy": name,
                    "verdict": "FAIL_MIN_TRADES",
                    "reason": f"No trades: {result.get('error', 'unknown')}",
                })
                continue

            trades = result["trades"]
            pnls = [t["pnl_cad"] for t in trades]

            print(f"  Out-of-sample trades: {len(pnls)}")
            print(f"  Total PnL: {sum(pnls):.2f} CAD")

            # Bootstrap CI
            bootstrap_result = bootstrap_ci(pnls, n_resamples=10000, seed=42)
            print(f"  Bootstrap CI: [{bootstrap_result.ci_lower:.2f}, {bootstrap_result.ci_upper:.2f}]")

            # Monte Carlo
            mc_result = monte_carlo_permutations(
                pnls,
                initial_equity=self.initial_equity_cad,
                n_simulations=10000,
                seed=42,
            )
            print(f"  P(DD>50%): {mc_result.prob_drawdown_50pct:.1%}")

            # Évaluer contre les critères
            from lab.validation.walk_forward import WalkForwardReport

            wf_report = WalkForwardReport(
                strategy_name=name,
                results=[],
                out_of_sample_trades=trades,
            )

            verdict = evaluate_strategy(name, strategy.timeframe, wf_report, bootstrap_result, mc_result)

            print(f"  Verdict: {verdict.verdict.name}")

            tournament_results.append({
                "strategy": name,
                "timeframe": strategy.timeframe,
                "verdict": verdict.verdict.name,
                "reason": verdict.details,
                "trades": len(pnls),
                "total_pnl": sum(pnls),
                "bootstrap_ci": {
                    "lower": bootstrap_result.ci_lower,
                    "mean": bootstrap_result.mean,
                    "upper": bootstrap_result.ci_upper,
                },
                "monte_carlo": {
                    "prob_dd_50pct": mc_result.prob_drawdown_50pct,
                    "final_equity": mc_result.final_equity_mean,
                },
            })

        return {
            "initial_equity_cad": self.initial_equity_cad,
            "usd_per_cad": self.usd_per_cad,
            "results": tournament_results,
            "passing": [r["strategy"] for r in tournament_results if r.get("verdict") == "PASS"],
        }


if __name__ == "__main__":
    runner = TournamentRunner(initial_equity_cad=200.0)
    results = runner.run_tournament()

    print("\n" + "=" * 60)
    print("TOURNAMENT SUMMARY")
    print("=" * 60)

    for r in results["results"]:
        print(f"{r['strategy']:20s} {r['verdict']:20s} {r.get('trades', 0)} trades")

    print(f"\nPassing strategies: {results['passing']}")

    # Save report
    report_path = Path("lab/reports/phase_d_tournament.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nReport saved to {report_path}")
