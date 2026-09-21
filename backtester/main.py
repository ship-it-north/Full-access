"""Point d'entrée : télécharge les données, lance les 6 combinaisons, écrit les rapports.

Exemples :
    python main.py                      # Bybit, univers top 30, 6 combinaisons
    python main.py --offline            # rejoue uniquement depuis le cache parquet
    python main.py --exchange okx       # même code sur un autre exchange ccxt
    python main.py --risk 0.02 --variant A
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

import config as C
import data as data_mod
from backtest import prepare_pair_frames, run_backtest
from report import export_trades, plot_equity, write_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backtester swing trading crypto")
    p.add_argument("--exchange", default=C.EXCHANGE_ID, help="id ccxt de l'exchange")
    p.add_argument("--offline", action="store_true", help="n'utilise que le cache parquet")
    p.add_argument("--no-refresh", action="store_true", help="pas de mise à jour du cache")
    p.add_argument("--universe-size", type=int, default=C.UNIVERSE_SIZE)
    p.add_argument("--pairs", nargs="*", default=None, help="symboles ccxt explicites")
    p.add_argument("--risk", type=float, nargs="*", default=list(C.RISK_LEVELS))
    p.add_argument("--variant", nargs="*", default=list(C.ENTRY_VARIANTS))
    p.add_argument("--workers", type=int, default=1, help="téléchargements parallèles")
    p.add_argument("--outdir", default=str(C.OUTPUT_DIR))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    C.EXCHANGE_ID = args.exchange
    outdir = Path(args.outdir)

    print(f"== Données ({args.exchange}) ==")
    raw = data_mod.load_universe(
        symbols=args.pairs,
        size=args.universe_size,
        refresh=not args.no_refresh,
        offline=args.offline,
        workers=args.workers,
    )
    if not raw:
        raise SystemExit("Aucune donnée disponible (cache vide ou exchange injoignable).")

    starts = [df.index[0] for df in raw.values()]
    ends = [df.index[-1] for df in raw.values()]
    data_range = (str(min(starts).date()), str(max(ends).date()))
    print(f"{len(raw)} paires, {data_range[0]} -> {data_range[1]}")

    print("\n== Précalcul des setups ==")
    t0 = time.time()
    base_cfg = C.StrategyConfig()
    prepared, timeline, skip_stats = prepare_pair_frames(raw, base_cfg)
    print(f"{len(prepared)} paires exploitables, {len(timeline)} barres, {time.time() - t0:.1f}s")
    setups_count = sum(sum(s is not None for s in d["setups"]) for d in prepared.values())
    print(f"{setups_count} barres avec setup valide")

    print("\n== Backtests ==")
    results = {}
    for variant in args.variant:
        for risk in args.risk:
            cfg = C.StrategyConfig(entry_variant=variant, risk_per_trade=risk)
            t0 = time.time()
            res = run_backtest(prepared, timeline, cfg)
            results[cfg.label] = res
            n = len(res.trades)
            final = res.equity_curve["equity"].iloc[-1] if not res.equity_curve.empty else C.INITIAL_CAPITAL
            flag = " [RUINE]" if res.ruined else ""
            print(f"  {cfg.label:<12} {n:>4} trades  capital final {final:>10.2f}$  "
                  f"({time.time() - t0:.1f}s){flag}")

    print("\n== Rapports ==")
    csv_path = export_trades(results, outdir)
    png_path = plot_equity(results, outdir / "equity_curves.png", C.INITIAL_CAPITAL)
    report_path = write_report(
        results, outdir, list(raw.keys()), args.exchange, data_range, skip_stats
    )
    print(f"  {csv_path}")
    print(f"  {png_path}")
    print(f"  {report_path}")

    print("\n" + pd.read_csv(outdir / "metrics_comparison.csv").to_string(index=False))


if __name__ == "__main__":
    main()
