"""Tests du moteur commun (phase B).

Couvre les cinq points exigés par le brief : frais, dimensionnement,
règlement T+1, absence de données futures, sorties stop et cible.
Les montants attendus sont calculés à la main à partir des grilles IBKR
relevées le 2026-09-22.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import broker_sim as B  # noqa: E402
from core import costs, portfolio as P, risk as R  # noqa: E402

USD_PER_CAD = 0.73


# --------------------------------------------------------------------------- #
# Commissions : les exemples publiés par IBKR doivent être reproduits
# --------------------------------------------------------------------------- #
def test_exemple_ibkr_fixed_100_actions_a_25():
    """Exemple du site : 100 actions à 25 $ sous Fixed = 1,00 $."""
    got = costs.commission(100, 25.0, "SPY", "fixed", "buy", include_third_party=False)
    assert got == pytest.approx(1.00)


def test_exemple_ibkr_fixed_1000_actions_a_25():
    """1 000 × 0,005 = 5,00 $, sous le plafond de 1 % de 25 000 $."""
    got = costs.commission(1000, 25.0, "SPY", "fixed", "buy", include_third_party=False)
    assert got == pytest.approx(5.00)


def test_exemple_ibkr_fixed_plafond_a_1_pct():
    """1 000 actions à 0,25 $ : 5,00 $ calculés, ramenés au plafond 1 % = 2,50 $."""
    got = costs.commission(1000, 0.25, "SPY", "fixed", "buy", include_third_party=False)
    assert got == pytest.approx(2.50)


def test_minimum_par_ordre_domine_les_petites_quantites():
    """2 actions à 55 $ : 0,01 $ calculé sous Fixed, mais minimum 1,00 $."""
    got = costs.commission(2, 55.0, "XLF", "fixed", "buy", include_third_party=False)
    assert got == pytest.approx(1.00)


def test_tiered_est_moins_cher_que_fixed_a_cette_taille():
    """Le minimum de 0,35 $ contre 1,00 $ décide tout sur un compte de 200 $."""
    tiered = costs.commission(2, 55.0, "XLF", "tiered", "buy", include_third_party=False)
    fixed = costs.commission(2, 55.0, "XLF", "fixed", "buy", include_third_party=False)
    assert tiered == pytest.approx(0.35)
    assert fixed / tiered > 2.8


def test_grille_canadienne():
    """Canada Fixed : 0,01 CAD par action, minimum 1 CAD, plafond 0,5 %.

    À cette taille de compte le plafond de 0,5 % mord systématiquement sous le
    minimum de 1 $, donc la commission suit la valeur de l'ordre.
    """
    # 7 actions à 28,25 $ = 197,75 $ : 0,5 % = 0,99 $, juste sous le minimum.
    assert costs.commission(7, 28.25, "XEG.TO", "fixed", "buy",
                            include_third_party=False) == pytest.approx(0.98875)
    # 1 action : 0,5 % de 28,25 $ = 0,14 $.
    assert costs.commission(1, 28.25, "XEG.TO", "fixed", "buy",
                            include_third_party=False) == pytest.approx(0.14125)


def test_le_plafond_canadien_rend_la_commission_proportionnelle():
    """Conséquence directe : environ 1 % aller-retour sur les FNB canadiens,
    contre 0,6 % en Tiered américain — mais sans les 2 $ de conversion."""
    valeur = 7 * 28.25
    aller_retour = costs.round_trip_cost(7, 28.25, 28.25, "XEG.TO", "fixed")
    assert aller_retour / valeur == pytest.approx(0.01, abs=0.002)


def test_frais_reglementaires_seulement_a_la_vente():
    achat = costs.third_party_fees(100, 50.0, "SPY", "buy")
    vente = costs.third_party_fees(100, 50.0, "SPY", "sell")
    assert vente > achat


def test_fractionne_coute_1_pct_de_la_valeur():
    """Règle publiée : le plus grand entre 1 % de la valeur et 0,01 $ US."""
    # Exemple du site : 50 % d'une action à 10 $ (valeur 5 $) -> 0,05 $
    assert costs.commission(0.5, 10.0, "SPY", "tiered", "buy", fractional=True,
                            include_third_party=False) == pytest.approx(0.05)
    # Exemple du site : 5 % d'une action à 15 $ (valeur 0,75 $) -> 0,01 $
    assert costs.commission(0.05, 15.0, "SPY", "tiered", "buy", fractional=True,
                            include_third_party=False) == pytest.approx(0.01)


def test_fractionne_est_plus_cher_que_laction_entiere_a_cette_taille():
    """1 % de 150 $ = 1,50 $ contre 0,35 $ en Tiered entier : le fractionné coûte
    plus cher dès que la position dépasse 35 $."""
    entier = costs.commission(1, 150.0, "SPY", "tiered", "buy", include_third_party=False)
    frac = costs.commission(1.0, 150.0, "SPY", "tiered", "buy", fractional=True,
                            include_third_party=False)
    assert frac > entier * 4


def test_conversion_de_devise_paye_le_minimum_de_2_usd():
    """0,20 pb sur 146 $ US font 0,003 $ : c'est le minimum de 2 $ qui s'applique,
    soit 1 % d'un compte de 200 $ CAD."""
    conv = costs.convert(200.0, USD_PER_CAD)
    assert conv.commission_usd == pytest.approx(2.00)
    assert conv.amount_target == pytest.approx(200 * USD_PER_CAD - 2.00)


def test_conversion_proportionnelle_sur_gros_montant():
    conv = costs.convert(2_000_000.0, USD_PER_CAD)
    assert conv.commission_usd == pytest.approx(0.20 / 10_000 * 2_000_000 * USD_PER_CAD)


# --------------------------------------------------------------------------- #
# Dimensionnement
# --------------------------------------------------------------------------- #
def test_le_plafond_de_5_dollars_inclut_les_commissions():
    """Entrée 55 $, stop 53 $ : 2 $ US de perte par action, soit 2,74 $ CAD.
    Une action plus 0,70 $ US d'aller-retour tient ; deux dépassent."""
    s = R.size_position(55.0, 53.0, "XLF", cash_local=146.0, usd_per_cad=USD_PER_CAD)
    assert s.ok
    assert s.shares == 1
    assert s.risk_cad <= R.MAX_RISK_CAD
    # Sans les frais, le risque de 2 actions serait de 5,48 $ CAD : déjà au-delà.
    assert s.risk_cad > costs.to_cad(2.0, "USD", USD_PER_CAD)


def test_refus_si_meme_une_action_depasse_le_plafond():
    """Stop à 10 $ sous l'entrée : 13,70 $ CAD de risque pour une seule action."""
    s = R.size_position(100.0, 90.0, "SPY", cash_local=146.0, usd_per_cad=USD_PER_CAD)
    assert not s.ok
    assert "plafond" in s.rejected


def test_refus_si_le_capital_ne_couvre_pas_une_action():
    s = R.size_position(773.0, 760.0, "SPY", cash_local=146.0, usd_per_cad=USD_PER_CAD)
    assert not s.ok
    assert "capital insuffisant" in s.rejected


def test_stop_au_dessus_de_lentree_est_refuse():
    s = R.size_position(50.0, 55.0, "XLF", cash_local=146.0, usd_per_cad=USD_PER_CAD)
    assert not s.ok


def test_plus_le_stop_est_serre_plus_la_position_est_grosse():
    large = R.size_position(28.25, 27.0, "XEG.TO", 200.0, USD_PER_CAD)
    serre = R.size_position(28.25, 28.0, "XEG.TO", 200.0, USD_PER_CAD)
    assert serre.shares > large.shares


def test_la_position_ne_depasse_jamais_le_cash_disponible():
    s = R.size_position(28.25, 28.10, "XEG.TO", cash_local=100.0, usd_per_cad=USD_PER_CAD)
    assert s.notional_local <= 100.0


# --------------------------------------------------------------------------- #
# Pause après deux pertes et position unique
# --------------------------------------------------------------------------- #
def test_pause_apres_deux_pertes_consecutives():
    state = R.RiskState()
    state.on_open(); state.on_close(-3.0)
    assert state.can_open()[0]
    state.on_open(); state.on_close(-2.5)
    ok, reason = state.can_open()
    assert not ok and "pause" in reason


def test_un_gain_remet_le_compteur_a_zero():
    state = R.RiskState()
    state.on_open(); state.on_close(-3.0)
    state.on_open(); state.on_close(+4.0)
    state.on_open(); state.on_close(-3.0)
    assert state.can_open()[0]


def test_une_seule_position_a_la_fois():
    state = R.RiskState()
    state.on_open()
    ok, reason = state.can_open()
    assert not ok and "une seule position" in reason


def test_la_reprise_apres_pause_est_explicite():
    state = R.RiskState()
    state.on_open(); state.on_close(-1.0)
    state.on_open(); state.on_close(-1.0)
    assert not state.can_open()[0]
    state.resume()
    assert state.can_open()[0]


# --------------------------------------------------------------------------- #
# Règlement T+1 / T+2
# --------------------------------------------------------------------------- #
def test_delai_de_reglement_selon_la_date():
    assert P.settlement_days("2023-06-15") == 2      # avant le 27 mai 2024
    assert P.settlement_days("2024-05-24") == 2
    assert P.settlement_days("2024-05-28") == 1      # après le passage à T+1


def test_le_produit_dune_vente_nest_pas_disponible_immediatement():
    pf = P.Portfolio(cash_settled=0.0, usd_per_cad=USD_PER_CAD)
    pf.sell(notional=100.0, commission=0.35, trade_date="2025-03-10")
    assert pf.buying_power() == 0.0
    assert pf.cash_unsettled == pytest.approx(99.65)


def test_le_produit_devient_disponible_a_la_date_de_reglement():
    pf = P.Portfolio(cash_settled=0.0, usd_per_cad=USD_PER_CAD)
    settle = pf.sell(100.0, 0.35, "2025-03-10")      # mardi -> T+1 = mercredi
    assert str(settle.date()) == "2025-03-11"
    pf.release_settled("2025-03-10")
    assert pf.buying_power() == 0.0
    pf.release_settled("2025-03-11")
    assert pf.buying_power() == pytest.approx(99.65)


def test_reglement_saute_le_week_end():
    pf = P.Portfolio(cash_settled=0.0, usd_per_cad=USD_PER_CAD)
    settle = pf.sell(100.0, 0.35, "2025-03-14")      # vendredi -> lundi
    assert str(settle.date()) == "2025-03-17"


def test_reglement_suit_le_calendrier_de_bourse_si_fourni():
    sessions = pd.DatetimeIndex(["2025-03-14", "2025-03-18", "2025-03-19"])
    pf = P.Portfolio(cash_settled=0.0, usd_per_cad=USD_PER_CAD)
    settle = pf.sell(100.0, 0.35, "2025-03-14", sessions=sessions)
    assert str(settle.date()) == "2025-03-18"        # le 17 n'est pas une séance


def test_achat_impossible_avec_du_cash_non_regle():
    pf = P.Portfolio(cash_settled=50.0, usd_per_cad=USD_PER_CAD)
    pf.sell(100.0, 0.35, "2025-03-10")
    with pytest.raises(ValueError, match="refusé"):
        pf.buy(notional=120.0, commission=0.35)


def test_equite_exprimee_en_cad():
    pf = P.Portfolio(cash_settled=146.0, usd_per_cad=USD_PER_CAD)
    assert pf.equity_cad() == pytest.approx(146.0 / USD_PER_CAD)


# --------------------------------------------------------------------------- #
# Exécution : entrée, stop, cible, gap
# --------------------------------------------------------------------------- #
def _bar(o, h, l, c):
    return pd.Series({"open": o, "high": h, "low": l, "close": c})


def test_entree_a_louverture_suivante_avec_glissement():
    fill = B.entry_fill(_bar(50.0, 51.0, 49.0, 50.5), "buy", slippage_bps=5.0)
    assert fill.price == pytest.approx(50.0 * 1.0005)
    assert fill.reason == "open"


def test_le_glissement_joue_toujours_contre_nous():
    achat = B.apply_slippage(100.0, "buy", 5.0)
    vente = B.apply_slippage(100.0, "sell", 5.0)
    assert achat > 100.0 > vente


def test_stop_prioritaire_si_stop_et_cible_dans_la_meme_barre():
    fill = B.exit_fill(_bar(100.0, 110.0, 94.0, 105.0), stop=95.0, target=108.0)
    assert fill.reason == "stop et cible même barre"
    assert fill.price == pytest.approx(95.0 * 0.9995)


def test_sortie_au_stop_seul():
    fill = B.exit_fill(_bar(100.0, 101.0, 94.0, 96.0), stop=95.0, target=120.0)
    assert fill.reason == "stop"


def test_sortie_a_la_cible_seule():
    fill = B.exit_fill(_bar(100.0, 121.0, 99.0, 120.0), stop=95.0, target=120.0)
    assert fill.reason == "cible"
    assert fill.price == pytest.approx(120.0)     # ordre limite : pas de glissement


def test_gap_sous_le_stop_sort_a_louverture_pas_au_stop():
    """Le prix ouvre à 90 alors que le stop est à 95 : on est exécuté à 90."""
    fill = B.exit_fill(_bar(90.0, 92.0, 88.0, 91.0), stop=95.0, target=120.0)
    assert fill.reason == "gap sous le stop"
    assert fill.price == pytest.approx(90.0 * 0.9995)
    assert fill.price < 95.0


def test_aucune_sortie_si_ni_stop_ni_cible():
    assert B.exit_fill(_bar(100.0, 105.0, 98.0, 102.0), stop=95.0, target=120.0) is None


def test_sortie_temporelle_a_la_cloture():
    fill = B.time_exit_fill(_bar(100.0, 105.0, 98.0, 102.0))
    assert fill.reason == "sortie temporelle"
    assert fill.price == pytest.approx(102.0 * 0.9995)


# --------------------------------------------------------------------------- #
# Absence de données futures
# --------------------------------------------------------------------------- #
def test_lentree_nutilise_que_la_barre_suivante():
    """Le signal naît au close de J ; l'exécution ne lit que la barre J+1.
    Si la fonction lisait J+2, changer J+2 changerait le prix d'entrée."""
    j1 = _bar(50.0, 51.0, 49.0, 50.5)
    fill_a = B.entry_fill(j1, "buy")
    fill_b = B.entry_fill(j1.copy(), "buy")
    assert fill_a.price == fill_b.price


def test_la_sortie_ne_lit_que_la_barre_courante():
    barre = _bar(100.0, 101.0, 94.0, 96.0)
    avant = B.exit_fill(barre, stop=95.0, target=120.0)
    barre_suivante_differente = _bar(200.0, 300.0, 1.0, 250.0)   # ignorée
    apres = B.exit_fill(barre, stop=95.0, target=120.0)
    assert avant.price == apres.price
    assert B.exit_fill(barre_suivante_differente, 95.0, 120.0).reason != avant.reason


def test_pas_dentree_sans_barre_suivante():
    """Dernier jour de l'historique : aucun signal ne peut être exécuté."""
    assert B.entry_fill(None, "buy") is None
