"""Lancer le backtest.

Exemples :
  python run.py --synthetic                                   # test du moteur (résultats sans valeur)
  python run.py --data-dir data --trade XLF XLE --benchmark SPY
  python run.py --data-dir data --trade XIU.TO --benchmark SPY --no-sensitivity
"""
import argparse
import itertools
import json
import os
import pandas as pd

from orb.config import Config
from orb import data as D
from orb.backtest import Backtester
from orb.metrics import compute, verdict


def load_events(path):
    if not path or not os.path.exists(path):
        return None
    ev = pd.read_csv(path, comment="#")
    if ev.empty:
        return None
    ev["datetime"] = pd.to_datetime(ev["datetime"]).dt.tz_localize(D.TZ)
    return ev


def run_once(data, trade, cfg, events):
    bt = Backtester(data, trade, cfg, events)
    return bt.run()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--trade", nargs="+", default=None, help="symboles à trader")
    ap.add_argument("--benchmark", default="SPY")
    ap.add_argument("--events", default="events.csv")
    ap.add_argument("--out", default="results")
    ap.add_argument("--oos-start", default=None)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--no-sensitivity", action="store_true")
    ap.add_argument("--tiered", action="store_true", help="grille IBKR Pro Tiered (0,0035 $/action, min 0,35 $ US) au lieu de Fixed")
    a = ap.parse_args()

    cfg = Config(benchmark=a.benchmark)
    if a.tiered:
        cfg = cfg.with_(usd_commission_per_share=0.0035, usd_commission_min=0.35)
    if a.oos_start:
        cfg = cfg.with_(oos_start=a.oos_start)

    if a.synthetic:
        trade = a.trade or ["SYN1", "SYN2"]
        data = D.synthetic([a.benchmark] + trade)
        for i, s in enumerate(trade):   # prix bas pour qu'un compte de 200 $ puisse acheter
            data[s][["open", "high", "low", "close"]] *= (45 + 10 * i) / data[s]["close"].iloc[0]
    else:
        if not a.trade:
            ap.error("--trade requis avec de vraies données")
        trade = a.trade
        data = D.load_dir(a.data_dir, sorted(set([a.benchmark] + trade)))

    os.makedirs(a.out, exist_ok=True)
    warns = []
    for s, df in data.items():
        warns += D.validate(df, s, cfg.bar_minutes)

    events = load_events(a.events)
    trades, signals, equity = run_once(data, trade, cfg, events)
    trades.to_csv(f"{a.out}/trades.csv", index=False)
    signals.to_csv(f"{a.out}/signals.csv", index=False)
    equity.to_csv(f"{a.out}/equity.csv", index=False)

    m_all = compute(trades, cfg.starting_cash_cad)
    m_is = compute(trades[trades["segment"] == "IS"] if not trades.empty else trades, cfg.starting_cash_cad)
    m_oos = compute(trades[trades["segment"] == "OOS"] if not trades.empty else trades, cfg.starting_cash_cad)

    # --- Sensibilité des paramètres ---
    sens_rows, pos_share = [], 0.0
    if not a.no_sensitivity:
        grid = itertools.product([15, 30], [1.5, 2.0, 3.0], [1.0, 1.2, 1.5])
        for orm, tr, vm in grid:
            c = cfg.with_(or_minutes=orm, target_r=tr, volume_mult=vm)
            t, _, _ = run_once(data, trade, c, events)
            row = {"or_minutes": orm, "target_r": tr, "volume_mult": vm}
            for seg in ["IS", "OOS"]:
                sub = t[t["segment"] == seg] if not t.empty else t
                mm = compute(sub, cfg.starting_cash_cad)
                row[f"{seg}_trades"] = mm.get("trades", 0)
                row[f"{seg}_exp_cad"] = mm.get("expectancy_cad")
                row[f"{seg}_pf"] = mm.get("profit_factor")
            sens_rows.append(row)
            print(f"  sensibilité OR={orm} R={tr} vol={vm} -> OOS exp {row['OOS_exp_cad']}")
        sens = pd.DataFrame(sens_rows)
        sens.to_csv(f"{a.out}/sensitivity.csv", index=False)
        valid = sens["OOS_exp_cad"].dropna()
        pos_share = float((valid > 0).mean()) if len(valid) else 0.0

    regimes = trades.groupby(["regime_trend", "regime_vol"])["pnl_cad"].agg(["count", "mean", "sum"]).round(2) \
        if not trades.empty else pd.DataFrame()
    n_regimes = int((regimes["count"] >= 5).sum()) if not regimes.empty else 0
    rej = signals[~signals["accepted"]]["reason"].value_counts() if not signals.empty else pd.Series(dtype=int)
    checks = verdict(m_all, m_oos, pos_share, n_regimes)
    go = all(ok for _, _, ok in checks)

    # --- Rapport ---
    L = ["# Rapport de backtest — ORB filtré par régime", ""]
    if a.synthetic:
        L += ["> **DONNÉES SYNTHÉTIQUES** : ce rapport vérifie seulement que le moteur fonctionne. Aucune conclusion possible.", ""]
    L += [f"Symboles tradés : {', '.join(trade)} · Benchmark : {cfg.benchmark} · Hors échantillon dès {cfg.oos_start}", ""]
    if warns:
        L += ["## Avertissements de données", *[f"- {w}" for w in warns], ""]
    L += ["## Verdict go / no-go", "", "| Critère | Résultat | OK |", "|---|---|---|"]
    L += [f"| {c} | {v} | {'✅' if ok else '❌'} |" for c, v, ok in checks]
    L += ["", f"**Décision : {'GO — passer au compte papier' if go else 'NO-GO — ne pas construire la suite tant que ce n’est pas réglé'}**", ""]
    L += ["## Métriques", "", "| Métrique | Total | In-sample | Hors échantillon |", "|---|---|---|---|"]
    for k in m_all:
        L.append(f"| {k} | {m_all.get(k)} | {m_is.get(k)} | {m_oos.get(k)} |")
    L += ["", "## Performance par régime (benchmark, veille)", "", regimes.to_markdown() if not regimes.empty else "_aucun trade_", ""]
    L += ["## Pourquoi les signaux ont été rejetés", "", rej.to_frame("n").to_markdown() if len(rej) else "_aucun rejet_", ""]
    if sens_rows:
        L += ["## Sensibilité des paramètres", "", pd.DataFrame(sens_rows).to_markdown(index=False), ""]
    L += ["## Paramètres", "", "```json", json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False), "```"]
    open(f"{a.out}/report.md", "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L[:40]))
    print(f"\nRapport complet : {a.out}/report.md")


if __name__ == "__main__":
    main()
