"""Graphiques et rapport markdown pour le système d'ensemble."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

# Palette catégorielle validée, ordre fixe (cf. report.py).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#1f1f1c", "#6b6a63", "#e3e2dc"
# Diverging : deux pôles + gris neutre au centre (corrélations).
DIVERGING = LinearSegmentedColormap.from_list("corr", ["#2a78d6", "#efeee6", "#eb6834"])


def _style(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, color=INK, fontsize=13, loc="left", pad=14)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=10)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)


def plot_walkforward(curves: dict[str, pd.Series], path: Path, log_scale: bool = True) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for color, (label, curve) in zip(SERIES, curves.items()):
        if curve.empty:
            continue
        ax.plot(curve.index, curve.values, color=color, linewidth=1.8, label=label)
        ax.annotate(label, (curve.index[-1], curve.iloc[-1]), color=color, fontsize=9,
                    xytext=(6, 0), textcoords="offset points", va="center")
    if log_scale:
        ax.set_yscale("log")
    _style(ax, "Walk-forward — équité hors échantillon vs benchmark",
           "Capital (USD, échelle log)" if log_scale else "Capital (USD)")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def plot_correlation(corr: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=150)
    fig.patch.set_facecolor("white")
    im = ax.imshow(corr.to_numpy(), cmap=DIVERGING, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=30, ha="right", color=MUTED, fontsize=9)
    ax.set_yticks(range(len(corr)), corr.index, color=MUTED, fontsize=9)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.iloc[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=9,
                        color=INK if abs(value) < 0.6 else "white")
    ax.set_title("Corrélation des rendements quotidiens entre composantes",
                 color=INK, fontsize=12, loc="left", pad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=MUTED, labelsize=8)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def plot_monte_carlo(finals: np.ndarray, p5: float, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.hist(finals * 100, bins=60, color=SERIES[0], edgecolor="white", linewidth=0.5)
    ax.axvline(p5 * 100, color=SERIES[1], linewidth=2.0)
    ax.annotate(f"5e percentile : {p5:.1%}", (p5 * 100, ax.get_ylim()[1] * 0.92),
                color=SERIES[1], fontsize=10, xytext=(8, 0), textcoords="offset points")
    ax.axvline(0, color=MUTED, linewidth=1.0, linestyle="--")
    _style(ax, "Monte Carlo — distribution du rendement final (1000 rééchantillonnages)",
           "Occurrences")
    ax.set_xlabel("Rendement final (%)", color=MUTED, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def plot_sensitivity(df: pd.DataFrame, path: Path) -> Path:
    """df : index = paramètre, colonnes = -30% / base / +30% (Sharpe walk-forward)."""
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    x = np.arange(len(df))
    width = 0.26
    for k, (col, color) in enumerate(zip(df.columns, SERIES)):
        ax.bar(x + (k - 1) * width, df[col].to_numpy(), width * 0.92, label=col, color=color)
    ax.set_xticks(x, df.index, rotation=20, ha="right")
    ax.axhline(0, color=MUTED, linewidth=1.0)
    _style(ax, "Sensibilité des paramètres — Sharpe hors échantillon", "Sharpe")
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, ncol=3, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def fmt_table(df: pd.DataFrame, pct_cols=()) -> str:
    if df.empty:
        return "_aucune donnée_"
    out = df.copy()
    for col in out.columns:
        if out[col].dtype.kind == "f":
            if col in pct_cols:
                out[col] = out[col].map(lambda v: "-" if pd.isna(v) else f"{v:.1%}")
            else:
                out[col] = out[col].map(lambda v: "-" if pd.isna(v) else f"{v:.2f}")
    return out.to_markdown(index=False)


PCT = ("win_rate", "rendement_total", "max_drawdown", "cagr", "vol_annualisee",
       "rendement_p5", "rendement_median", "rendement_p95", "rendement_moyen",
       "maxdd_p5", "maxdd_median", "proba_perte", "proba_ruine_80pct")
