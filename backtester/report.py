"""Métriques, tableaux comparatifs, export CSV et courbe d'équité."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402
from backtest import BacktestResult  # noqa: E402

# Palette catégorielle validée (ordre fixe, jamais cyclé) — 6 combinaisons max.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK = "#1f1f1c"
MUTED = "#6b6a63"
GRID = "#e3e2dc"

TRADE_CSV_COLUMNS = [
    "entry_time", "exit_time", "pair", "variant", "entry_price", "initial_stop",
    "target", "exit_price", "exit_reason", "r_multiple", "net_pnl", "gross_pnl",
    "fees", "funding", "bars_held", "qty", "notional", "risk_amount",
    "rr_planned", "b_price", "a_price", "l1", "l2", "moved_to_breakeven",
    "size_capped", "equity_after",
]


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def longest_losing_streak(r: pd.Series) -> int:
    best = current = 0
    for value in r:
        if value < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def compute_metrics(
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    initial_capital: float,
    label: str = "",
) -> dict:
    if trades.empty:
        return {
            "combinaison": label, "trades": 0, "win_rate": np.nan, "R_moyen": np.nan,
            "esperance_R": np.nan, "R_moyen_gagnant": np.nan, "R_moyen_perdant": np.nan,
            "profit_factor": np.nan, "rendement_total": 0.0, "capital_final": initial_capital,
            "max_drawdown": 0.0, "serie_perdante_max": 0, "duree_moyenne_h": np.nan,
            "trades_bridés": 0,
        }

    r = trades["r_multiple"]
    wins = trades[trades["net_pnl"] > 0]
    losses = trades[trades["net_pnl"] <= 0]
    gross_win = wins["net_pnl"].sum()
    gross_loss = abs(losses["net_pnl"].sum())
    win_rate = len(wins) / len(trades)
    avg_win_r = wins["r_multiple"].mean() if len(wins) else 0.0
    avg_loss_r = losses["r_multiple"].mean() if len(losses) else 0.0

    if not equity_curve.empty:
        equity = equity_curve["equity"]
        final_equity = float(equity.iloc[-1])
        dd = max_drawdown(equity)
    else:
        final_equity = float(initial_capital + trades["net_pnl"].sum())
        dd = max_drawdown(pd.Series([initial_capital] + list(trades["equity_after"])))

    return {
        "combinaison": label,
        "trades": int(len(trades)),
        "win_rate": float(win_rate),
        "R_moyen": float(r.mean()),
        # Espérance = p(gain)·R_moyen_gagnant + p(perte)·R_moyen_perdant.
        "esperance_R": float(win_rate * avg_win_r + (1 - win_rate) * avg_loss_r),
        "R_moyen_gagnant": float(avg_win_r),
        "R_moyen_perdant": float(avg_loss_r),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else np.inf,
        "rendement_total": float(final_equity / initial_capital - 1.0),
        "capital_final": final_equity,
        "max_drawdown": float(dd),
        "serie_perdante_max": int(longest_losing_streak(r)),
        "duree_moyenne_h": float(trades["bars_held"].mean()),
        "trades_bridés": int(trades["size_capped"].sum()),
    }


def comparison_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = [
        compute_metrics(res.trades, res.equity_curve, res.config.initial_capital, label)
        for label, res in results.items()
    ]
    return pd.DataFrame(rows)


def split_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """Métriques séparées in-sample (2023-2024) / out-of-sample (2025+)."""
    rows = []
    for label, res in results.items():
        trades = res.trades
        for period, start, end in (
            ("in-sample", C.IS_START, C.IS_END),
            ("out-of-sample", C.OOS_START, C.OOS_END),
        ):
            if trades.empty:
                subset = trades
                curve = res.equity_curve.iloc[0:0]
            else:
                mask = (trades["entry_time"] >= pd.Timestamp(start, tz="UTC")) & (
                    trades["entry_time"] <= pd.Timestamp(end, tz="UTC")
                )
                subset = trades[mask]
                curve = res.equity_curve.loc[
                    (res.equity_curve.index >= pd.Timestamp(start, tz="UTC"))
                    & (res.equity_curve.index <= pd.Timestamp(end, tz="UTC"))
                ]
            capital = float(curve["equity"].iloc[0]) if not curve.empty else res.config.initial_capital
            metrics = compute_metrics(subset, curve, capital, label)
            metrics["periode"] = period
            rows.append(metrics)
    df = pd.DataFrame(rows)
    cols = ["combinaison", "periode"] + [c for c in df.columns if c not in ("combinaison", "periode")]
    return df[cols]


def per_pair_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = []
    for label, res in results.items():
        if res.trades.empty:
            continue
        for pair, group in res.trades.groupby("pair"):
            wins = (group["net_pnl"] > 0).sum()
            rows.append({
                "combinaison": label,
                "paire": pair,
                "trades": len(group),
                "win_rate": wins / len(group),
                "R_total": group["r_multiple"].sum(),
                "R_moyen": group["r_multiple"].mean(),
                "pnl_net": group["net_pnl"].sum(),
            })
    df = pd.DataFrame(rows)
    return df.sort_values(["combinaison", "R_total"], ascending=[True, False]) if not df.empty else df


def exit_reason_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = []
    for label, res in results.items():
        if res.trades.empty:
            continue
        counts = res.trades["exit_reason"].value_counts()
        row = {"combinaison": label, **counts.to_dict()}
        rows.append(row)
    return pd.DataFrame(rows).fillna(0)


def plot_equity(results: dict[str, BacktestResult], path: Path, initial_capital: float) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for color, (label, res) in zip(SERIES_COLORS, results.items()):
        curve = res.equity_curve
        if curve.empty:
            continue
        ax.plot(curve.index, curve["equity"], color=color, linewidth=1.8, label=label)

    ax.axhline(initial_capital, color=MUTED, linewidth=1.0, linestyle="--", zorder=0)
    ax.set_yscale("log")
    ax.set_ylabel("Capital (USD, échelle log)", color=MUTED, fontsize=10)
    ax.set_title(
        "Courbe d'équité — 2 variantes d'entrée × 3 niveaux de risque",
        color=INK, fontsize=13, loc="left", pad=14,
    )
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, ncol=3, loc="upper left")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def export_trades(results: dict[str, BacktestResult], outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    frames = []
    for label, res in results.items():
        if res.trades.empty:
            continue
        df = res.trades.copy()
        df.insert(0, "combinaison", label)
        cols = ["combinaison"] + [c for c in TRADE_CSV_COLUMNS if c in df.columns]
        df = df[cols]
        df.to_csv(outdir / f"trades_{label}.csv", index=False)
        frames.append(df)
    all_path = outdir / "trades_all.csv"
    if frames:
        pd.concat(frames).to_csv(all_path, index=False)
    else:
        pd.DataFrame(columns=["combinaison"] + TRADE_CSV_COLUMNS).to_csv(all_path, index=False)
    return all_path


def _fmt(df: pd.DataFrame) -> str:
    formatted = df.copy()
    for col in formatted.columns:
        if formatted[col].dtype.kind == "f":
            if col in {"win_rate", "rendement_total", "max_drawdown"}:
                formatted[col] = formatted[col].map(lambda v: "-" if pd.isna(v) else f"{v:.1%}")
            else:
                formatted[col] = formatted[col].map(lambda v: "-" if pd.isna(v) else f"{v:.2f}")
    return formatted.to_markdown(index=False)


def write_report(
    results: dict[str, BacktestResult],
    outdir: Path,
    universe: list[str],
    exchange_id: str,
    data_range: tuple[str, str],
    skip_stats: dict,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    comp = comparison_table(results)
    split = split_table(results)
    pairs = per_pair_table(results)
    exits = exit_reason_table(results)

    comp.to_csv(outdir / "metrics_comparison.csv", index=False)
    split.to_csv(outdir / "metrics_is_oos.csv", index=False)
    if not pairs.empty:
        pairs.to_csv(outdir / "metrics_per_pair.csv", index=False)

    lines = [
        "# Backtest swing crypto — rapport",
        "",
        f"- Exchange : **{exchange_id}** (perps {C.QUOTE}, marché `{C.MARKET_TYPE}`)",
        f"- Timeframe : {C.TIMEFRAME} — période couverte : {data_range[0]} → {data_range[1]}",
        f"- Univers : {len(universe)} paires",
        f"- Capital initial : {C.INITIAL_CAPITAL:.0f} $ — risque par trade : "
        + ", ".join(f"{r:.0%}" for r in C.RISK_LEVELS),
        f"- Frictions : maker {C.MAKER_FEE:.3%}, taker {C.TAKER_FEE:.3%}, "
        f"funding {C.FUNDING_RATE_8H:.2%}/8h, slippage stop {C.STOP_SLIPPAGE:.2%}",
        "",
        "## Comparatif des 6 combinaisons",
        "",
        _fmt(comp),
        "",
        "## Split in-sample / out-of-sample",
        "",
        _fmt(split),
        "",
        "## Raisons de sortie",
        "",
        exits.to_markdown(index=False) if not exits.empty else "_aucun trade_",
        "",
        "## Décomposition par paire",
        "",
        _fmt(pairs) if not pairs.empty else "_aucun trade_",
        "",
        "## Motifs de rejet des setups (diagnostic)",
        "",
        pd.DataFrame(
            sorted(skip_stats.items(), key=lambda kv: -kv[1]), columns=["motif", "barres"]
        ).to_markdown(index=False),
        "",
        "## Univers",
        "",
        ", ".join(universe),
        "",
    ]
    path = outdir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
