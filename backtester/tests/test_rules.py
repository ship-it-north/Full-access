"""Tests du moteur de règles sur des données synthétiques à réponse connue.

Chaque test construit une série où le résultat attendu est calculable à la main.
Le dernier bloc vérifie explicitement l'absence de look-ahead (invariance par préfixe).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import prepare_pair_frames, run_backtest  # noqa: E402
from config import StrategyConfig  # noqa: E402
from rules import (  # noqa: E402
    Pivot,
    build_setup,
    check_entry_levels,
    cluster_lows,
    find_new_high,
    find_pivots,
    leg_origin,
    scan_setups,
    select_l1_l2,
    sma,
    strong_levels,
    trend_change,
    trend_filter,
)

CFG = StrategyConfig()
TINY = StrategyConfig(
    trend_lookback=10,
    sma_period=5,
    new_high_lookback=20,
    new_high_max_age=10,
    support_lookback=60,
    pivot_left=2,
    pivot_right=2,
    pivot_confirm_lag=2,
)


# --------------------------------------------------------------------------- #
# Indicateurs
# --------------------------------------------------------------------------- #
def test_sma_valeurs_connues():
    got = sma([1, 2, 3, 4, 5], 3)
    assert np.isnan(got[0]) and np.isnan(got[1])
    assert got[2] == pytest.approx(2.0)
    assert got[3] == pytest.approx(3.0)
    assert got[4] == pytest.approx(4.0)


def test_trend_change_sur_lookback():
    close = [100.0] * 5 + [150.0]  # +50% sur 5 barres
    got = trend_change(close, 5)
    assert np.isnan(got[4])
    assert got[5] == pytest.approx(0.5)


def test_trend_filter_bornes_30_100_pct():
    cfg = StrategyConfig(trend_lookback=3, sma_period=2)
    # +20% : sous la borne basse -> rejeté ; +50% : accepté ; +150% : rejeté.
    for change, expected in ((0.20, False), (0.50, True), (1.50, False)):
        close = [100.0, 100.0, 100.0, 100.0 * (1 + change)]
        assert trend_filter(close, cfg)[3] is np.True_ if expected else True
        assert bool(trend_filter(close, cfg)[3]) == expected


def test_trend_filter_exige_close_au_dessus_de_la_sma():
    cfg = StrategyConfig(trend_lookback=3, sma_period=3)
    close = [100.0, 200.0, 190.0, 150.0]  # +50% sur 3 barres mais sous la SMA(3)=163.3
    assert bool(trend_filter(close, cfg)[3]) is False


# --------------------------------------------------------------------------- #
# Pivots
# --------------------------------------------------------------------------- #
def test_pivot_haut_position_et_confirmation():
    cfg = StrategyConfig(pivot_left=2, pivot_right=2, pivot_confirm_lag=2)
    high = [1, 2, 5, 2, 1, 0.5, 0.4]  # sommet en index 2
    low = [1, 1, 1, 1, 1, 1, 1]
    highs, _ = find_pivots(high, low, cfg)
    assert [p.index for p in highs] == [2]
    assert highs[0].confirm_index == 4  # 2 barres plus tard
    assert highs[0].price == 5


def test_pivot_bas_symetrique():
    cfg = StrategyConfig(pivot_left=2, pivot_right=2, pivot_confirm_lag=2)
    low = [5, 4, 1, 4, 5, 6, 7]
    high = [9, 9, 9, 9, 9, 9, 9]
    _, lows = find_pivots(high, low, cfg)
    assert [p.index for p in lows] == [2]
    assert lows[0].price == 1


def test_pivot_5_5_par_defaut_ne_detecte_rien_sur_bordures():
    high = [1, 2, 3, 4, 5, 9, 5, 4, 3, 2, 1]  # sommet en index 5, exactement 5/5
    low = [0] * 11
    highs, _ = find_pivots(high, low, CFG)
    assert [p.index for p in highs] == [5]
    assert highs[0].confirm_index == 10  # utilisable seulement à la barre 10


def test_pivot_ignore_les_egalites():
    cfg = StrategyConfig(pivot_left=2, pivot_right=2, pivot_confirm_lag=2)
    high = [1, 2, 5, 5, 1, 0.5, 0.4]  # double sommet : pas de pivot strict
    low = [0] * 7
    highs, _ = find_pivots(high, low, cfg)
    assert highs == []


# --------------------------------------------------------------------------- #
# Nouveau sommet B
# --------------------------------------------------------------------------- #
def test_new_high_recent_accepte():
    cfg = StrategyConfig(new_high_lookback=10, new_high_max_age=5)
    high = [1, 2, 3, 4, 5, 6, 7, 20, 9, 10]  # max en index 7, âge = 2
    got = find_new_high(high, 9, cfg)
    assert got == (7, 20.0)


def test_new_high_trop_ancien_rejete():
    cfg = StrategyConfig(new_high_lookback=10, new_high_max_age=5)
    high = [20, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # max en index 0, âge = 9 >= 5
    assert find_new_high(high, 9, cfg) is None


def test_new_high_historique_insuffisant():
    cfg = StrategyConfig(new_high_lookback=10, new_high_max_age=5)
    assert find_new_high([1, 2, 3], 2, cfg) is None


# --------------------------------------------------------------------------- #
# Clustering des supports
# --------------------------------------------------------------------------- #
def _lows(prices, start=0):
    return [Pivot(start + k, start + k, p, "low") for k, p in enumerate(prices)]


def test_cluster_regroupe_sous_1_pct_et_moyenne():
    # 100 et 100.5 (+0.5%) fusionnent ; 110 est isolé.
    levels = cluster_lows(_lows([100.0, 100.5, 110.0]), CFG)
    assert len(levels) == 2
    assert levels[0].price == pytest.approx(100.25)
    assert levels[0].touches == 2
    assert levels[1].touches == 1


def test_cluster_separe_au_dela_de_1_pct():
    levels = cluster_lows(_lows([100.0, 101.5]), CFG)  # +1.5% > 1%
    assert [lv.touches for lv in levels] == [1, 1]


def test_niveau_fort_exige_2_touches():
    levels = cluster_lows(_lows([100.0, 100.5, 110.0]), CFG)
    fortes = strong_levels(levels, CFG)
    assert len(fortes) == 1
    assert fortes[0].price == pytest.approx(100.25)


def test_selection_l1_l2():
    levels = cluster_lows(_lows([80.0, 80.2, 90.0, 90.3, 95.0, 95.4]), CFG)
    fortes = strong_levels(levels, CFG)
    l1, l2 = select_l1_l2(fortes, price=100.0)
    assert l1.price == pytest.approx(95.2)
    assert l2.price == pytest.approx(90.15)


def test_selection_l1_l2_sans_niveau_sous_le_prix():
    levels = strong_levels(cluster_lows(_lows([120.0, 120.5]), CFG), CFG)
    l1, l2 = select_l1_l2(levels, price=100.0)
    assert l1 is None and l2 is None


# --------------------------------------------------------------------------- #
# Point A et filtres d'entrée
# --------------------------------------------------------------------------- #
def test_leg_origin_prend_le_dernier_pivot_bas_confirme_avant_b():
    lows = [Pivot(10, 15, 50.0, "low"), Pivot(30, 35, 60.0, "low"), Pivot(80, 85, 70.0, "low")]
    a = leg_origin(lows, b_index=50, bar_index=60)
    assert a.index == 30


def test_leg_origin_ignore_un_pivot_non_encore_confirme():
    lows = [Pivot(10, 15, 50.0, "low"), Pivot(30, 99, 60.0, "low")]
    a = leg_origin(lows, b_index=50, bar_index=60)  # le pivot 30 n'est confirmé qu'en 99
    assert a.index == 10


def test_skip_si_stop_trop_loin():
    # entrée 100, stop 90 -> 10% > 8%
    assert check_entry_levels(100.0, 90.0, 130.0, CFG) == "stop_too_far"


def test_skip_si_rr_insuffisant():
    # entrée 100, stop 95 (5%), cible 106 -> R:R = 1.2 < 1.5
    assert check_entry_levels(100.0, 95.0, 106.0, CFG) == "rr_too_low"


def test_setup_accepte_si_rr_suffisant():
    # entrée 100, stop 95, cible 110 -> R:R = 2.0
    assert check_entry_levels(100.0, 95.0, 110.0, CFG) is None


# --------------------------------------------------------------------------- #
# Setup complet sur une série construite à la main
# --------------------------------------------------------------------------- #
def _serie_setup_valide():
    """Série où le setup attendu est connu : L1≈100, L2≈95, B=130, A=100.

    - 40 barres de base oscillant autour de 100 avec 2 creux à 95 et 2 creux à 100 ;
    - une jambe haussière jusqu'à 130 (B) ;
    - un repli vers 104 qui laisse le prix au-dessus de L1.
    """
    rng = np.random.default_rng(0)
    highs, lows, closes = [], [], []

    def bar(h, l, c):
        highs.append(h)
        lows.append(l)
        closes.append(c)

    for _ in range(6):
        bar(103, 102, 102.5)
    # creux L2 #1 à 95
    bar(102, 95.0, 99)
    for _ in range(6):
        bar(104, 101, 103)
    # creux L2 #2 à 95.3 (< 1% de 95 -> même cluster)
    bar(102, 95.3, 99)
    for _ in range(6):
        bar(106, 103, 105)
    # creux L1 #1 à 100
    bar(105, 100.0, 103)
    for _ in range(6):
        bar(108, 104, 107)
    # creux L1 #2 à 100.4
    bar(107, 100.4, 104)
    for _ in range(6):
        bar(110, 106, 109)
    # jambe haussière vers B = 130
    for px in (112, 116, 120, 124, 128, 130, 127, 124, 120, 116, 112, 108, 106):
        bar(px + 1, px - 1, px)
    for _ in range(10):
        bar(107, 104, 105.5)
    return np.array(highs, float), np.array(lows, float), np.array(closes, float)


def test_build_setup_sur_serie_connue():
    cfg = StrategyConfig(
        trend_lookback=5, sma_period=5, new_high_lookback=20, new_high_max_age=20,
        support_lookback=100, pivot_left=2, pivot_right=2, pivot_confirm_lag=2,
        max_stop_distance=0.10, min_rr=1.0,
    )
    high, low, close = _serie_setup_valide()
    _, pivot_lows = find_pivots(high, low, cfg)
    i = len(close) - 1
    setup, reason = build_setup(high, low, close, i, pivot_lows, cfg, trend_ok=True)
    assert reason == "ok", reason
    assert setup.l1 == pytest.approx(100.2, abs=0.05)   # moyenne 100.0 / 100.4
    assert setup.l2 == pytest.approx(95.15, abs=0.05)   # moyenne 95.0 / 95.3
    assert setup.stop == pytest.approx(95.15 * 0.997, abs=0.05)
    assert setup.b_price == pytest.approx(131.0)        # high de la bougie à 130
    assert setup.leg == pytest.approx(setup.b_price - setup.a_price)
    # cible = entrée + (B - A)
    assert setup.ref_target == pytest.approx(setup.l1 + setup.leg)


def test_build_setup_rejette_si_pas_de_l2():
    cfg = StrategyConfig(pivot_left=2, pivot_right=2, pivot_confirm_lag=2,
                         support_lookback=100, new_high_lookback=10, new_high_max_age=10)
    n = 40
    high = np.full(n, 105.0)
    low = np.full(n, 104.0)
    close = np.full(n, 104.5)
    high[20] = 130.0  # sommet récent
    # un seul cluster de creux
    low[5] = 100.0
    low[12] = 100.3
    _, pivot_lows = find_pivots(high, low, cfg)
    setup, reason = build_setup(high, low, close, 25, pivot_lows, cfg, trend_ok=True)
    assert setup is None
    assert reason in {"no_l2", "no_l1"}


def test_build_setup_rejette_si_trend_filter_ko():
    high, low, close = _serie_setup_valide()
    setup, reason = build_setup(high, low, close, len(close) - 1, [], CFG, trend_ok=False)
    assert setup is None and reason == "trend_filter"


# --------------------------------------------------------------------------- #
# Non-look-ahead : invariance par préfixe
# --------------------------------------------------------------------------- #
def _serie_aleatoire(n=1200, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0008, 0.01, n))
    high = close * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.004, n)))
    return high, low, close


def test_aucun_look_ahead_invariance_par_prefixe():
    """Le setup calculé à la barre i doit être identique avec ou sans les barres > i.

    C'est la vérification décisive : si une fonction lisait le futur, tronquer la
    série changerait le résultat sur la barre i.
    """
    cfg = TINY
    high, low, close = _serie_aleatoire()
    complet, _, _ = scan_setups(high, low, close, cfg)
    for cut in (300, 600, 900, 1100):
        tronque, _, _ = scan_setups(high[:cut], low[:cut], close[:cut], cfg)
        for i in range(cut):
            a, b = complet[i], tronque[i]
            assert (a is None) == (b is None), f"divergence None/Setup en i={i} (cut={cut})"
            if a is not None:
                assert a.l1 == pytest.approx(b.l1), f"L1 diverge en i={i} (cut={cut})"
                assert a.stop == pytest.approx(b.stop), f"stop diverge en i={i}"
                assert a.b_price == pytest.approx(b.b_price), f"B diverge en i={i}"
                assert a.a_price == pytest.approx(b.a_price), f"A diverge en i={i}"


def test_pivot_jamais_utilise_avant_confirmation():
    cfg = TINY
    high, low, close = _serie_aleatoire(600, seed=3)
    _, pivot_lows = find_pivots(high, low, cfg)
    for i in range(len(close)):
        setup, _ = build_setup(high, low, close, i, pivot_lows, cfg, trend_ok=True)
        if setup is None:
            continue
        assert setup.a_index + cfg.pivot_confirm_lag <= i
        assert setup.b_index <= i


# --------------------------------------------------------------------------- #
# Moteur de backtest : scénarios déterministes
# --------------------------------------------------------------------------- #
def _frame(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def _moteur_avec_setup(setup, rows, cfg):
    """Injecte un setup figé à la barre 0 et déroule les barres suivantes."""
    df = _frame(rows)
    prepared = {
        "TEST": {
            "index": df.index,
            "open": df["open"].to_numpy(float),
            "high": df["high"].to_numpy(float),
            "low": df["low"].to_numpy(float),
            "close": df["close"].to_numpy(float),
            "setups": [setup] + [None] * (len(df) - 1),
            "trend": np.ones(len(df), dtype=bool),
            "pos": {ts: i for i, ts in enumerate(df.index)},
        }
    }
    return run_backtest(prepared, df.index, cfg)


def _setup_simple(l1=100.0, l2=95.0, leg=20.0, b_price=130.0):
    from rules import Setup

    stop = l2 * 0.997
    return Setup(
        bar_index=0, l1=l1, l2=l2, stop=stop, b_index=0, b_price=b_price,
        a_index=0, a_price=b_price - leg, leg=leg, ref_entry=l1,
        ref_target=l1 + leg, ref_rr=(l1 + leg - l1) / (l1 - stop),
    )


def test_variante_a_remplie_puis_cible_touchee():
    cfg = StrategyConfig(entry_variant="A", risk_per_trade=0.02, max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],   # barre 0 : armement
        [101, 101, 99, 100.5],  # barre 1 : low 99 <= L1=100 -> remplie à 100
        [101, 121, 100.5, 120], # barre 2 : high 121 >= cible 120 -> sortie cible
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    assert t.entry_price == pytest.approx(100.0)
    assert t.exit_reason == "target"
    assert t.exit_price == pytest.approx(120.0)
    assert t.r_multiple > 3.5  # R:R planifié = 20 / 5.3 ≈ 3.77, moins les frais


def test_variante_a_stoppee():
    cfg = StrategyConfig(entry_variant="A", max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 100.5],
        [100, 100.5, 90, 92],  # traverse le stop à 94.715
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    t = res.trades.iloc[0]
    assert t.exit_reason == "stop"
    assert t.exit_price == pytest.approx(94.715 * (1 - 0.0005), rel=1e-6)
    assert t.r_multiple < -1.0  # pire que -1R à cause du slippage et des frais


def test_stop_et_cible_dans_la_meme_bougie_compte_une_perte():
    cfg = StrategyConfig(entry_variant="A", max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 100.5],
        [100, 125, 90, 110],  # touche stop ET cible
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    t = res.trades.iloc[0]
    assert t.exit_reason == "stop_and_target_same_bar"
    assert t.net_pnl < 0


def test_variante_b_attend_la_cloture_haussiere():
    cfg = StrategyConfig(entry_variant="B", max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],     # armement
        [101, 101, 99, 99.5],     # touche L1 mais clôture sous L1 -> pas d'entrée
        [99.5, 100.2, 99, 99.8],  # clôture haussière mais sous L1 -> pas d'entrée
        [99.8, 103, 99.7, 102],   # clôture haussière > L1 -> entrée à 102
        [102, 125, 101, 124],     # cible = 102 + 20 = 122 touchée
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    assert t.entry_price == pytest.approx(102.0)
    assert t.target == pytest.approx(122.0)
    assert t.exit_reason == "target"


def test_variante_b_expire_apres_3_barres():
    cfg = StrategyConfig(entry_variant="B", max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 99.5],       # touche
        [99.5, 99.8, 99, 99.2],     # +1 : pas de confirmation
        [99.2, 99.9, 99, 99.4],     # +2
        [99.4, 99.9, 99, 99.5],     # +3
        [99.5, 103, 99.4, 102.5],   # +4 : hors fenêtre, et le low ne retouche pas L1
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    assert res.trades.empty


def test_time_stop_a_120_barres():
    cfg = StrategyConfig(entry_variant="A", time_stop_bars=5, max_stop_distance=0.10)
    rows = [[101, 102, 101, 101], [101, 101, 99, 100.5]]
    rows += [[100.5, 101, 99.5, 100.5]] * 6  # ni stop ni cible
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    t = res.trades.iloc[0]
    assert t.exit_reason == "time_stop"
    assert t.bars_held == 5


def test_breakeven_apres_cloture_au_dessus_de_b():
    """B=110 et cible=130 : la clôture au-dessus de B arme le breakeven sans toucher la cible."""
    cfg = StrategyConfig(entry_variant="A", max_stop_distance=0.10)
    setup = _setup_simple(leg=30.0, b_price=110.0)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 100.5],       # entrée à 100, cible 130
        [100.5, 112, 100.5, 111],    # clôture > B=110 -> stop remonté à l'entrée
        [111, 111.5, 99, 100],       # repasse sous l'entrée -> sortie breakeven
    ]
    res = _moteur_avec_setup(setup, rows, cfg)
    t = res.trades.iloc[0]
    assert bool(t.moved_to_breakeven) is True
    assert t.exit_reason == "breakeven_stop"
    assert t.exit_price == pytest.approx(100.0 * (1 - 0.0005))
    assert -0.05 < t.r_multiple < 0  # ~0 brut, légèrement négatif après frais


def test_breakeven_ne_sapplique_pas_a_la_barre_qui_larme():
    """La clôture > B est connue au close : le nouveau stop ne peut pas agir avant."""
    cfg = StrategyConfig(entry_variant="A", max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 100.5],
        [100.5, 112, 99.9, 111],  # low 99.9 < entrée 100 mais breakeven pas encore armé
        [111, 111.2, 110, 111],
    ]
    res = _moteur_avec_setup(_setup_simple(leg=30.0, b_price=110.0), rows, cfg)
    assert res.trades.empty  # toujours en position, pas de sortie prématurée


def test_sizing_sur_la_distance_au_stop():
    cfg = StrategyConfig(entry_variant="A", risk_per_trade=0.02, initial_capital=100.0,
                         max_stop_distance=0.10)
    rows = [[101, 102, 101, 101], [101, 101, 99, 100.5], [101, 121, 100.5, 120]]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    t = res.trades.iloc[0]
    # risque 2$ / distance (100 - 94.715) = 5.285 -> qty ≈ 0.3784
    assert t.risk_amount == pytest.approx(2.0)
    assert t.qty == pytest.approx(2.0 / (100 - 95 * 0.997), rel=1e-6)


def test_un_seul_trade_par_paire_et_max_5_positions():
    cfg = StrategyConfig(entry_variant="A", max_concurrent=2, max_stop_distance=0.10)
    setup = _setup_simple()
    rows = [[101, 102, 101, 101], [101, 101, 99, 100.5]] + [[100.5, 101, 100, 100.5]] * 3
    df = _frame(rows)
    prepared = {}
    for pair in ("AAA", "BBB", "CCC"):
        prepared[pair] = {
            "index": df.index,
            "open": df["open"].to_numpy(float),
            "high": df["high"].to_numpy(float),
            "low": df["low"].to_numpy(float),
            "close": df["close"].to_numpy(float),
            "setups": [setup] + [None] * (len(df) - 1),
            "trend": np.ones(len(df), dtype=bool),
            "pos": {ts: i for i, ts in enumerate(df.index)},
        }
    res = run_backtest(prepared, df.index, StrategyConfig(
        entry_variant="A", max_concurrent=2, max_stop_distance=0.10, time_stop_bars=2))
    assert len(res.trades) == 2  # la 3e paire n'a jamais eu de slot
    assert set(res.trades["pair"]) == {"AAA", "BBB"}


def test_frictions_appliquees():
    """Un aller-retour au même prix doit être perdant du montant des frictions."""
    cfg = StrategyConfig(entry_variant="A", time_stop_bars=2, max_stop_distance=0.10)
    rows = [
        [101, 102, 101, 101],
        [101, 101, 99, 100.5],           # entrée à 100
        [100, 100.5, 99.5, 100],
        [100, 100.5, 99.5, 100.0],       # time stop à 100 = prix d'entrée
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    t = res.trades.iloc[0]
    assert t.gross_pnl == pytest.approx(0.0, abs=1e-9)
    assert t.fees > 0 and t.funding > 0
    assert t.net_pnl == pytest.approx(-(t.fees + t.funding))


def test_entree_impossible_avant_la_barre_darmement():
    """Un setup détecté au close de la barre i ne peut jamais être exécuté sur i."""
    cfg = StrategyConfig(entry_variant="A", max_stop_distance=0.10)
    rows = [
        [101, 102, 99, 101],  # cette barre touche déjà L1=100 mais le setup naît à son close
        [101, 102, 101, 101],
    ]
    res = _moteur_avec_setup(_setup_simple(), rows, cfg)
    assert res.trades.empty
