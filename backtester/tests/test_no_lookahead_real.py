"""Vérification de non-look-ahead sur les données réelles mises en cache.

Ces tests sont ignorés si le cache parquet est vide (aucun réseau requis).

Trois contrôles complémentaires :
  1. invariance par préfixe : tronquer la série ne change aucun setup passé ;
  2. causalité des trades : sortie >= entrée, entrée > barre d'armement du setup ;
  3. rejeu incrémental : un backtest sur les N premières barres produit exactement
     les mêmes trades que le backtest complet restreint à cette fenêtre.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C  # noqa: E402
from backtest import prepare_pair_frames, run_backtest  # noqa: E402
from rules import scan_setups  # noqa: E402


def _cached_pairs(limit: int = 3) -> dict[str, pd.DataFrame]:
    paths = sorted(C.DATA_DIR.glob(f"*_{C.TIMEFRAME}.parquet"))[:limit]
    return {p.stem: pd.read_parquet(p) for p in paths}


pytestmark = pytest.mark.skipif(
    not sorted(C.DATA_DIR.glob(f"*_{C.TIMEFRAME}.parquet")),
    reason="aucune donnée en cache",
)


def test_invariance_par_prefixe_sur_donnees_reelles():
    cfg = C.StrategyConfig()
    for name, df in _cached_pairs(2).items():
        df = df.iloc[:4000]
        high, low, close = (df[c].to_numpy() for c in ("high", "low", "close"))
        complet, _, _ = scan_setups(high, low, close, cfg)
        cut = 3000
        tronque, _, _ = scan_setups(high[:cut], low[:cut], close[:cut], cfg)
        for i in range(cut):
            a, b = complet[i], tronque[i]
            assert (a is None) == (b is None), f"{name} : divergence en i={i}"
            if a is not None:
                assert a.l1 == pytest.approx(b.l1)
                assert a.stop == pytest.approx(b.stop)
                assert a.b_price == pytest.approx(b.b_price)
                assert a.a_price == pytest.approx(b.a_price)


def test_causalite_des_trades():
    cfg = C.StrategyConfig(entry_variant="A", risk_per_trade=0.02)
    prepared, timeline, _ = prepare_pair_frames(_cached_pairs(5), cfg)
    if not prepared:
        pytest.skip("historique insuffisant")
    res = run_backtest(prepared, timeline, cfg)
    if res.trades.empty:
        pytest.skip("aucun trade sur cet échantillon")
    assert (res.trades["exit_index"] >= res.trades["entry_index"]).all()
    assert (res.trades["exit_time"] >= res.trades["entry_time"]).all()
    assert (res.trades["bars_held"] <= cfg.time_stop_bars).all()
    # Le prix d'entrée est toujours dans le range de la bougie d'entrée.
    for _, t in res.trades.iterrows():
        data = prepared[t["pair"]]
        i = int(t["entry_index"])
        assert data["low"][i] <= t["entry_price"] <= data["high"][i]


def test_rejeu_incremental_identique():
    """Rejouer sur une fenêtre tronquée doit redonner les mêmes trades."""
    cfg = C.StrategyConfig(entry_variant="A", risk_per_trade=0.02)
    pairs = _cached_pairs(4)
    prepared, timeline, _ = prepare_pair_frames(pairs, cfg)
    if not prepared:
        pytest.skip("historique insuffisant")
    full = run_backtest(prepared, timeline, cfg)
    if full.trades.empty:
        pytest.skip("aucun trade sur cet échantillon")

    cut_ts = timeline[int(len(timeline) * 0.7)]
    truncated = {k: df.loc[df.index <= cut_ts] for k, df in pairs.items()}
    prep_t, tl_t, _ = prepare_pair_frames(truncated, cfg)
    partial = run_backtest(prep_t, tl_t, cfg)

    # Trades entièrement clos avant la coupure : doivent coïncider exactement.
    ref = full.trades[full.trades["exit_time"] <= cut_ts]
    got = partial.trades[partial.trades["exit_time"] <= cut_ts]
    assert len(ref) == len(got), f"{len(ref)} trades complets vs {len(got)} en rejeu"
    cols = ["pair", "entry_time", "entry_price", "exit_time", "exit_price", "exit_reason"]
    pd.testing.assert_frame_equal(
        ref[cols].reset_index(drop=True), got[cols].reset_index(drop=True)
    )
