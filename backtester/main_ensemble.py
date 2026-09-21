"""Orchestration des 3 phases du système par ensemble.

    python main_ensemble.py --offline            # rejoue depuis le cache parquet
    python main_ensemble.py --fixed-universe     # univers figé (mesure du biais de survivance)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
import data as data_mod
import ensemble as E
import report_ensemble as R
import signals as S
import validation as V

IS_END = pd.Timestamp("2024-12-31", tz="UTC")
OOS_START = pd.Timestamp("2025-01-01", tz="UTC")

# Univers figé de référence : 10 paires listées avant 2023, pour quantifier
# le biais de survivance face à l'univers point-in-time.
FIXED_10 = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT", "XRP/USDT:USDT",
    "ADA/USDT:USDT", "DOGE/USDT:USDT", "LTC/USDT:USDT", "LINK/USDT:USDT", "AVAX/USDT:USDT",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Système de signaux par ensemble")
    p.add_argument("--exchange", default="okx")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--outdir", default=str(C.OUTPUT_DIR))
    p.add_argument("--mc-runs", type=int, default=1000)
    p.add_argument("--skip-sensitivity", action="store_true")
    return p.parse_args()


# --------------------------------------------------------------------------- #
# Données et univers
# --------------------------------------------------------------------------- #
def monthly_universe(top_n: int = 30) -> dict[pd.Timestamp, list[str]]:
    """Top N par volume quote moyen sur 30 jours, reconstruit à chaque 1er du mois."""
    panel = pd.read_parquet(C.DATA_DIR / f"{C.EXCHANGE_ID}_daily_quote_volume.parquet")
    vol30 = panel.rolling(30, min_periods=20).mean()
    dates = [d for d in pd.date_range(panel.index[0], panel.index[-1], freq="MS", tz="UTC")
             if d in vol30.index]
    return {d: vol30.loc[d].dropna().nlargest(top_n).index.tolist() for d in dates}


def membership_mask(index: pd.DatetimeIndex, pairs: list[str],
                    universe: dict[pd.Timestamp, list[str]]) -> pd.DataFrame:
    """Matrice booléenne : la paire appartient-elle au top 30 en vigueur à cette barre."""
    mask = pd.DataFrame(False, index=index, columns=pairs)
    dates = sorted(universe)
    for k, start in enumerate(dates):
        end = dates[k + 1] if k + 1 < len(dates) else index[-1] + pd.Timedelta(hours=1)
        members = [p for p in universe[start] if p in mask.columns]
        if members:
            mask.loc[(mask.index >= start) & (mask.index < end), members] = True
    return mask


def load_frames(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol in symbols:
        safe = symbol.replace("/", "_").replace(":", "_")
        path = C.DATA_DIR / f"{C.EXCHANGE_ID}_{safe}_{C.TIMEFRAME}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if len(df) > 400 * 24:  # au moins ~400 jours pour que les signaux existent
                out[symbol] = df
    return out


def load_funding(symbols: list[str], offline: bool, workers: int) -> dict[str, pd.Series]:
    out = {}
    missing = []
    for symbol in symbols:
        safe = symbol.replace("/", "_").replace(":", "_")
        path = C.DATA_DIR / f"{C.EXCHANGE_ID}_{safe}_funding.parquet"
        if path.exists():
            out[symbol] = pd.read_parquet(path)["funding"]
        else:
            missing.append(symbol)
    if missing and not offline:
        out.update(data_mod.load_funding(missing, workers=workers))
    return out


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #
def phase1(panels, corr_cube, outdir: Path) -> dict:
    print("\n=== PHASE 1 — composantes isolées ===")
    names = S.SIGNAL_NAMES
    full = V.run_components(panels, corr_cube, names)
    is_ = V.run_components(panels, corr_cube, names, end=IS_END)
    oos = V.run_components(panels, corr_cube, names, start=OOS_START)

    rows = []
    for period, results in (("complet", full), ("in-sample", is_), ("out-of-sample", oos)):
        for name, res in results.items():
            m = E.metrics(res, name)
            m["periode"] = period
            rows.append(m)
    table = pd.DataFrame(rows)
    table = table[["strategie", "periode"] + [c for c in table.columns
                                              if c not in ("strategie", "periode")]]
    table.to_csv(outdir / "phase1_composantes.csv", index=False)

    corr_full = V.correlation_matrix(full)
    corr_oos = V.correlation_matrix(oos)
    corr_full.to_csv(outdir / "phase1_correlations.csv")
    kept, log = V.select_components(oos)
    for line in log:
        print("  " + line)
    return {"table": table, "corr_full": corr_full, "corr_oos": corr_oos,
            "kept": kept, "log": log, "results_oos": oos}


def phase2(panels, corr_cube, kept: list[str], outdir: Path) -> pd.DataFrame:
    print("\n=== PHASE 2 — ensemble et sizing (période de développement) ===")
    if not kept:
        return pd.DataFrame()
    weights = tuple((name, 1.0) for name in kept)
    filters = tuple(S.FILTER_NAMES)
    rows = []
    for threshold in (0.3, 0.5, 0.7):
        for sizing, label in (("voltarget", "vol-target 20%/vol, cap 5%"), ("fixed", "fixe 2%")):
            cfg = E.EnsembleConfig(weights=weights, filters=filters, threshold=threshold,
                                   sizing=sizing, label=f"seuil {threshold} | {label}")
            res = E.run_ensemble(panels, cfg, corr_cube, end=IS_END)
            V.record_trial(E.sharpe(res.daily_returns))
            m = E.metrics(res, cfg.label)
            m["risque_moyen_pct"] = (float(res.trades.risk_pct.mean())
                                     if not res.trades.empty else np.nan)
            m["pct_trades_au_plafond"] = (
                float((res.trades.risk_pct >= cfg.max_risk - 1e-9).mean())
                if sizing == "voltarget" and not res.trades.empty else np.nan
            )
            rows.append(m)
            print(f"  {cfg.label:<42} trades {m['trades']:>4}  Sharpe {m['sharpe']:>6.2f}")
    table = pd.DataFrame(rows)
    table.to_csv(outdir / "phase2_ensemble.csv", index=False)
    return table


def phase3(panels, corr_cube, frames, outdir: Path, args) -> dict:
    print("\n=== PHASE 3 — validation ===")
    print("\n[3.1] Walk-forward glissant (train 12 m / test 3 m, pas 3 m)")
    equity, trades, folds = V.walk_forward(panels, corr_cube, S.SIGNAL_NAMES)

    btc = None
    for candidate in ("BTC/USDT:USDT", "BTC_USDT_USDT"):
        if candidate in frames:
            btc = frames[candidate]["close"]
            break
    curves = {"Ensemble (walk-forward)": equity}
    bench_rows = [V.curve_metrics(equity, "Ensemble (walk-forward, test only)")]
    if btc is not None and not equity.empty:
        bh = V.buy_and_hold(btc.loc[equity.index[0]:equity.index[-1]], 100.0)
        curves["BTC buy & hold"] = bh
        bench_rows.append(V.curve_metrics(bh, "BTC buy & hold"))
    bench = pd.DataFrame(bench_rows)
    bench.insert(1, "trades", [len(trades)] + [0] * (len(bench_rows) - 1))
    bench.to_csv(outdir / "phase3_benchmark.csv", index=False)
    print(R.fmt_table(bench, R.PCT))

    exposure = V.exposure_stats(trades, equity)
    if exposure:
        print(f"  temps en position {exposure['temps_en_position']:.1%} | "
              f"meilleur mois = {exposure['part_du_meilleur_mois']:.0%} du P&L total")

    print("\n[3.3] Monte Carlo")
    mc = V.monte_carlo(trades, n_runs=args.mc_runs)
    if mc:
        print(f"  rendement p5 {mc['rendement_p5']:.1%} | médian {mc['rendement_median']:.1%} "
              f"| P(perte) {mc['proba_perte']:.0%}")

    # Le DSR est calculé en fin de run : il doit compter TOUTES les configurations,
    # y compris celles des analyses de sensibilité qui suivent.
    n_selection = E.RUN_COUNTER["n"]

    sensitivity = pd.DataFrame()
    cost_table = pd.DataFrame()
    if not args.skip_sensitivity:
        print("\n[3.5] Sensibilité aux paramètres (±30%)")
        sensitivity = run_sensitivity(panels, corr_cube, frames)
        sensitivity.to_csv(outdir / "phase3_sensibilite.csv")
        print(R.fmt_table(sensitivity.reset_index()))

        print("\n[3.6] Sensibilité aux coûts")
        rows = []
        for mult, label in ((1.0, "coûts nominaux"), (2.0, "frais et slippage doublés")):
            eq, tr, _ = V.walk_forward(panels, corr_cube, S.SIGNAL_NAMES,
                                       base_config={"cost_mult": mult}, verbose=False)
            m = V.curve_metrics(eq, label)
            m["trades"] = len(tr)
            rows.append(m)
        cost_table = pd.DataFrame(rows)
        cost_table.to_csv(outdir / "phase3_couts.csv", index=False)
        print(R.fmt_table(cost_table, R.PCT))

    return {"equity": equity, "trades": trades, "folds": folds, "curves": curves,
            "benchmark": bench, "mc": mc, "n_selection": n_selection,
            "exposure": exposure, "sensitivity": sensitivity, "costs": cost_table}


def run_sensitivity(panels, corr_cube, frames) -> pd.DataFrame:
    """±30% sur chaque paramètre : Sharpe walk-forward (donc hors échantillon)."""
    rows = {}
    base_eq, _, _ = V.walk_forward(panels, corr_cube, S.SIGNAL_NAMES, verbose=False)
    base_sharpe = V.curve_metrics(base_eq, "base")["sharpe"]

    for param, value in V.SENSITIVITY_PARAMS.items():
        row = {}
        for factor, label in ((0.7, "-30%"), (1.0, "base"), (1.3, "+30%")):
            if factor == 1.0:
                row[label] = base_sharpe
                continue
            cfg = {param: V.scale_param(value, factor)}
            eq, _, _ = V.walk_forward(panels, corr_cube, S.SIGNAL_NAMES,
                                      base_config=cfg, verbose=False)
            row[label] = V.curve_metrics(eq, label)["sharpe"]
        rows[param] = row
        print(f"  {param:<16} -30% {row['-30%']:>6.2f} | base {row['base']:>6.2f} "
              f"| +30% {row['+30%']:>6.2f}")

    for param, value in V.SIGNAL_PARAMS.items():
        row = {}
        for factor, label in ((0.7, "-30%"), (1.0, "base"), (1.3, "+30%")):
            if factor == 1.0:
                row[label] = base_sharpe
                continue
            perturbed = S.build_panels(frames, FUNDING_CACHE, {param: V.scale_param(value, factor)})
            if "membership" in panels:
                perturbed["membership"] = panels["membership"]
            eq, _, _ = V.walk_forward(perturbed, corr_cube, S.SIGNAL_NAMES, verbose=False)
            row[label] = V.curve_metrics(eq, label)["sharpe"]
        rows[param] = row
        print(f"  {param:<16} -30% {row['-30%']:>6.2f} | base {row['base']:>6.2f} "
              f"| +30% {row['+30%']:>6.2f}")
    return pd.DataFrame(rows).T[["-30%", "base", "+30%"]]


FUNDING_CACHE: dict[str, pd.Series] = {}


def main() -> None:
    args = parse_args()
    C.EXCHANGE_ID = args.exchange
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("== Univers point-in-time ==")
    universe = monthly_universe()
    union = sorted({s for members in universe.values() for s in members})
    frames = load_frames(union)
    print(f"{len(union)} paires dans l'union, {len(frames)} avec assez d'historique")

    global FUNDING_CACHE
    FUNDING_CACHE = load_funding(list(frames), args.offline, args.workers)
    print(f"funding disponible pour {len(FUNDING_CACHE)}/{len(frames)} paires")

    t0 = time.time()
    panels = S.build_panels(frames, FUNDING_CACHE)
    panels["membership"] = membership_mask(panels["close"].index, list(panels["close"].columns),
                                           universe)
    corr_cube = E.rolling_correlations(panels["close"])
    print(f"panels construits en {time.time() - t0:.0f}s "
          f"({panels['close'].shape[0]} barres × {panels['close'].shape[1]} paires)")

    p1 = phase1(panels, corr_cube, outdir)
    p2 = phase2(panels, corr_cube, p1["kept"], outdir)
    p3 = phase3(panels, corr_cube, frames, outdir, args)

    print("\n[3.4] Deflated Sharpe Ratio (après comptage complet des configurations)")
    equity = p3["equity"]
    daily = (equity.resample("1D").last().dropna().pct_change().dropna()
             if not equity.empty else pd.Series(dtype=float))
    dsr_rows = []
    for n_trials, label in ((p3["n_selection"], "configurations de sélection"),
                            (E.RUN_COUNTER["n"], "toutes configurations évaluées")):
        d = V.deflated_sharpe(daily, n_trials, V.TRIAL_SHARPES)
        if d:
            d["comptage"] = label
            dsr_rows.append(d)
            print(f"  N={d['n_configurations']:<5} ({label}) : Sharpe {d['sharpe_annualise']:.2f} "
                  f"| seuil hasard {d['sharpe_seuil_hasard_annualise']:.2f} "
                  f"| DSR {d['deflated_sharpe_ratio']:.3f}")
    p3["dsr_table"] = pd.DataFrame(dsr_rows)
    p3["dsr"] = dsr_rows[-1] if dsr_rows else {}

    print("\n=== Biais de survivance : univers figé de 10 paires ===")
    fixed_frames = load_frames(FIXED_10)
    survivorship = pd.DataFrame()
    if fixed_frames:
        fixed_panels = S.build_panels(fixed_frames, FUNDING_CACHE)
        fixed_corr = E.rolling_correlations(fixed_panels["close"])
        eq_fixed, tr_fixed, _ = V.walk_forward(fixed_panels, fixed_corr, S.SIGNAL_NAMES,
                                               verbose=False)
        rows = [V.curve_metrics(p3["equity"], "univers point-in-time (top 30 mensuel)"),
                V.curve_metrics(eq_fixed, f"univers figé ({len(fixed_frames)} paires pré-2023)")]
        survivorship = pd.DataFrame(rows)
        survivorship.to_csv(outdir / "phase3_survivance.csv", index=False)
        print(R.fmt_table(survivorship, R.PCT))
        p3["curves"][f"Univers figé ({len(fixed_frames)} paires)"] = eq_fixed

    write_report(outdir, p1, p2, p3, survivorship, universe, frames)
    print(f"\nRapport : {outdir / 'report_ensemble.md'}")
    print(f"Configurations évaluées au total : {E.RUN_COUNTER['n']}")


def caveats(p1, p3) -> list[str]:
    """Limites qui relativisent les chiffres ci-dessus — à lire avant le verdict."""
    trades = p3["trades"]
    lines = [
        "1. **Paires délistées absentes.** L'univers point-in-time est reconstruit à "
        "partir des volumes quotidiens réels à chaque date, donc le *classement* est "
        "causal. Mais il ne peut contenir que des paires encore cotées aujourd'hui : "
        "celles délistées entre 2023 et 2026 sont invisibles. Le biais de survivance "
        "est réduit, pas éliminé.",
        "2. **La règle de sélection de la phase 1 regarde l'out-of-sample.** C'est ce "
        "que demande la consigne, mais sélectionner sur la période de test est en soi "
        "une fuite. C'est pourquoi la phase 3 refait la sélection dans chaque fenêtre "
        "d'entraînement : seuls ces chiffres-là sont exploitables.",
    ]
    if not trades.empty:
        lines.append(
            f"3. **Échantillon minuscule.** {len(trades)} trades hors échantillon sur "
            f"{len(p3['folds'])} fenêtres. À ce volume, l'intervalle de confiance du "
            "Sharpe couvre largement zéro ; aucune des métriques n'a de puissance "
            "statistique."
        )
        if "risk_pct" in trades:
            au_plafond = float((trades["risk_pct"] >= 0.05 - 1e-9).mean())
            lines.append(
                f"4. **Le sizing vol-target ne mord jamais.** `20% / vol réalisée` "
                f"dépasse le plafond de 5% dès que la vol annualisée est sous 400% — "
                f"le cas de toutes les cryptos liquides. {au_plafond:.0%} des trades "
                "sont au plafond, donc le sizing « vol-target » est en pratique un "
                "sizing fixe à 5% et la comparaison avec le fixe 2% ne teste que le "
                "niveau de levier, pas l'adaptation à la volatilité."
            )
    lines.append(
        f"{len(lines) + 1}. **Exchange.** Bybit est géo-bloqué depuis l'environnement "
        "d'exécution ; le run tourne sur OKX avec le même code."
    )
    return lines


def recommendation(p1, p3, survivorship, beats_btc: bool) -> list[str]:
    """Verdict dérivé mécaniquement des critères, pas d'appréciation libre."""
    dsr = p3.get("dsr") or {}
    mc = p3.get("mc") or {}
    sens = p3.get("sensitivity")
    n_trades = len(p3["trades"])

    checks = []
    oos_rows = p1["table"][p1["table"]["periode"] == "out-of-sample"]
    best_oos = float(oos_rows["sharpe"].max()) if not oos_rows.empty else float("nan")
    kept_txt = ", ".join(p1["kept"]) if p1["kept"] else "aucune"
    checks.append((
        "Phase 1 : au moins une composante passe Sharpe > 0.3 en OOS",
        bool(p1["kept"]),
        f"retenues : {kept_txt} (meilleur Sharpe OOS : {best_oos:.2f})",
    ))
    checks.append((
        "Le système bat BTC buy & hold en Sharpe",
        bool(beats_btc),
        f"{p3['benchmark'].iloc[0]['sharpe']:.2f} contre "
        f"{p3['benchmark'].iloc[1]['sharpe']:.2f} pour BTC"
        if len(p3["benchmark"]) > 1 else "benchmark indisponible",
    ))
    checks.append((
        "Deflated Sharpe Ratio > 0.95",
        bool(dsr.get("deflated_sharpe_ratio", 0) > 0.95),
        f"DSR = {dsr.get('deflated_sharpe_ratio', float('nan')):.3f} avec "
        f"N = {dsr.get('n_configurations', 0)} configurations "
        f"(seuil de hasard : Sharpe {dsr.get('sharpe_seuil_hasard_annualise', float('nan')):.2f})",
    ))
    checks.append((
        "Monte Carlo : 5e percentile du rendement positif",
        bool(mc.get("rendement_p5", -1) > 0),
        f"p5 = {mc.get('rendement_p5', float('nan')):.1%}, "
        f"P(perte) = {mc.get('proba_perte', float('nan')):.0%}"
        if mc else "pas assez de trades",
    ))
    if sens is not None and not sens.empty:
        spread = float((sens.max(axis=1) - sens.min(axis=1)).max())
        worst = sens.min().min()
        checks.append((
            "Sensibilité : aucune perturbation ±30% ne fait passer le Sharpe sous 0",
            bool(worst >= 0),
            f"pire Sharpe observé {worst:.2f} ; amplitude max {spread:.2f} "
            f"(paramètre le plus instable : {(sens.max(axis=1) - sens.min(axis=1)).idxmax()})",
        ))
    checks.append((
        "Échantillon suffisant (>= 100 trades hors échantillon)",
        n_trades >= 100,
        f"{n_trades} trades sur toutes les fenêtres de test",
    ))

    passed = sum(1 for _, ok, _ in checks if ok)
    lines = ["| Critère | Verdict | Mesure |", "|---|---|---|"]
    for name, ok, detail in checks:
        lines.append(f"| {name} | {'OUI' if ok else 'NON'} | {detail} |")
    lines.append("")
    verdict = "DÉPLOYER" if passed == len(checks) else "NE PAS DÉPLOYER"
    lines.append(f"**Recommandation : {verdict}** "
                 f"({passed}/{len(checks)} critères remplis).")
    if passed < len(checks):
        lines.append("")
        lines.append("Les critères non remplis ne sont pas des détails de calibration : "
                     "ils disent que l'edge mesuré n'est pas distinguable du bruit de "
                     "sélection. Augmenter le nombre de configurations essayées ne ferait "
                     "que dégrader davantage le DSR.")
    if not survivorship.empty and len(survivorship) > 1:
        lines.append("")
        lines.append(
            f"À noter : sur un univers figé de majors pré-2023, le même système donne un "
            f"Sharpe de {survivorship.iloc[1]['sharpe']:.2f} contre "
            f"{survivorship.iloc[0]['sharpe']:.2f} sur l'univers rotatif. "
            "La performance vient donc entièrement de la rotation vers les paires "
            "récemment devenues liquides, pas d'un edge sur les actifs établis."
        )
    return lines


def write_report(outdir, p1, p2, p3, survivorship, universe, frames) -> None:
    charts = []
    if p3["curves"]:
        charts.append(R.plot_walkforward(p3["curves"], outdir / "walkforward_equity.png"))
    if not p1["corr_full"].empty:
        charts.append(R.plot_correlation(p1["corr_full"], outdir / "correlation_matrix.png"))
    if p3["mc"]:
        charts.append(R.plot_monte_carlo(p3["mc"]["finals"], p3["mc"]["rendement_p5"],
                                         outdir / "monte_carlo.png"))
    if not p3["sensitivity"].empty:
        charts.append(R.plot_sensitivity(p3["sensitivity"], outdir / "sensitivity.png"))

    folds_table = pd.DataFrame([{
        "test": f"{f.test_start.date()} → {f.test_end.date()}",
        **{f"SR {k.split('_')[0]}": v for k, v in f.component_sharpes.items()},
        "retenues": "+".join(f.selected) or "aucune",
        "seuil": f.threshold,
    } for f in p3["folds"]])

    mc = p3["mc"]
    dsr = p3["dsr"]
    equity = p3["equity"]
    bench = p3["benchmark"]

    sys_sharpe = bench.iloc[0]["sharpe"] if len(bench) else np.nan
    btc_sharpe = bench.iloc[1]["sharpe"] if len(bench) > 1 else np.nan
    beats_btc = np.isfinite(sys_sharpe) and np.isfinite(btc_sharpe) and sys_sharpe > btc_sharpe

    lines = [
        "# Système de signaux par ensemble — rapport de validation",
        "",
        f"- Données : {C.EXCHANGE_ID} perps USDT, {C.TIMEFRAME}, "
        f"{equity.index[0].date() if not equity.empty else '?'} → "
        f"{equity.index[-1].date() if not equity.empty else '?'} (fenêtres de test concaténées)",
        f"- Univers point-in-time : top 30 par volume 30 j reconstruit chaque mois "
        f"({len(universe)} rééquilibrages, {len(frames)} paires exploitables dans l'union)",
        f"- Configurations évaluées au total : **{E.RUN_COUNTER['n']}**",
        "",
        "## Phase 1 — composantes isolées",
        "",
        "Chaque composante est backtestée seule, sans filtre de régime, avec un sizing "
        "fixe à 2% pour que la comparaison soit à armes égales.",
        "",
        R.fmt_table(p1["table"], R.PCT),
        "",
        "### Matrice de corrélation des rendements quotidiens (période complète)",
        "",
        p1["corr_full"].round(2).to_markdown() if not p1["corr_full"].empty else "_n/a_",
        "",
        "### Application de la règle de sélection (Sharpe > 0.3 OOS, corrélation < 0.6)",
        "",
        *[f"- {line}" for line in p1["log"]],
        "",
        f"**Composantes retenues : {', '.join(p1['kept']) if p1['kept'] else 'AUCUNE'}**",
        "",
        "## Phase 2 — ensemble et sizing",
        "",
        R.fmt_table(p2, R.PCT) if not p2.empty else
        "_Aucune composante retenue : pas d'ensemble à construire._",
        "",
        "## Phase 3 — validation",
        "",
        "### 3.1 Walk-forward glissant (train 12 mois / test 3 mois, pas 3 mois)",
        "",
        "La sélection des composantes et du seuil est refaite **dans chaque fenêtre "
        "d'entraînement**, puis appliquée telle quelle aux 3 mois suivants. "
        "Les chiffres ci-dessous ne contiennent que des fenêtres de test.",
        "",
        R.fmt_table(folds_table),
        "",
        "### 3.2 Benchmark",
        "",
        R.fmt_table(bench, R.PCT),
        "",
        f"**{'Le système bat BTC en Sharpe.' if beats_btc else 'Le système ne bat PAS BTC en Sharpe.'}**",
        "",
        "### 3.2b Exposition réelle",
        "",
        "Le Sharpe walk-forward doit se lire avec le temps réellement passé en marché : "
        "la plupart des folds ne retiennent aucune composante, donc le capital reste à plat.",
        "",
        R.fmt_table(pd.DataFrame([p3["exposure"]]), R.PCT + ("temps_en_position", "part_du_meilleur_mois"))
        if p3.get("exposure") else "_n/a_",
        "",
        "### 3.3 Monte Carlo (1000 rééchantillonnages de la séquence de trades)",
        "",
        R.fmt_table(pd.DataFrame([{k: v for k, v in mc.items() if k != 'finals'}]), R.PCT)
        if mc else "_pas assez de trades_",
        "",
        "### 3.4 Deflated Sharpe Ratio",
        "",
        "Le DSR est la probabilité que le Sharpe observé soit supérieur à ce qu'on "
        "obtiendrait par pure chance compte tenu du nombre de configurations essayées. "
        "Un DSR proche de 1 valide, proche de 0 invalide.",
        "",
        R.fmt_table(p3.get("dsr_table", pd.DataFrame())) if len(p3.get("dsr_table", pd.DataFrame())) else "_n/a_",
        "",
        "### 3.5 Sensibilité aux paramètres (±30%, Sharpe walk-forward)",
        "",
        R.fmt_table(p3["sensitivity"].reset_index().rename(columns={"index": "paramètre"}))
        if not p3["sensitivity"].empty else "_non exécuté_",
        "",
        "### 3.6 Sensibilité aux coûts",
        "",
        R.fmt_table(p3["costs"], R.PCT) if not p3["costs"].empty else "_non exécuté_",
        "",
        "### Biais de survivance",
        "",
        R.fmt_table(survivorship, R.PCT) if not survivorship.empty else "_n/a_",
        "",
        "## Réserves méthodologiques",
        "",
        *caveats(p1, p3),
        "",
        "## Recommandation finale",
        "",
        *recommendation(p1, p3, survivorship, beats_btc),
        "",
        "## Graphiques",
        "",
        *[f"- `{Path(c).name}`" for c in charts],
        "",
    ]
    (outdir / "report_ensemble.md").write_text("\n".join(lines), encoding="utf-8")
    if not p3["trades"].empty:
        p3["trades"].to_csv(outdir / "walkforward_trades.csv", index=False)
    json.dump(
        {"configurations": E.RUN_COUNTER["n"], "kept": p1["kept"],
         "dsr": {k: v for k, v in (dsr or {}).items()}},
        open(outdir / "ensemble_summary.json", "w"), indent=2, default=float,
    )


if __name__ == "__main__":
    main()
