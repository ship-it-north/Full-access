"""Tests de la couche données (phase A).

Aucun appel réseau : les fournisseurs sont testés sur leur logique locale
(pacing, découpage, refus explicite) et le reste sur des séries construites
à la main dont la réponse est connue.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import cache, config as C, events as EV, quality, universe  # noqa: E402
from data.providers.alpaca import AlpacaProvider  # noqa: E402
from data.providers.base import ProviderUnavailable  # noqa: E402
from data.providers.ibkr import IBKRProvider, Pacer, chunk_ranges  # noqa: E402
from data.providers.yahoo import YahooProvider  # noqa: E402


def _ohlcv(n=60, start="2023-01-02", price=100.0, freq="B"):
    idx = pd.date_range(start, periods=n, freq=freq)
    close = pd.Series(np.linspace(price, price * 1.1, n), index=idx)
    return pd.DataFrame({
        "open": close * 0.999, "high": close * 1.01, "low": close * 0.99,
        "close": close, "adj_close": close, "volume": 1_000_000.0,
    }, index=idx)


# --------------------------------------------------------------------------- #
# Cache et provenance
# --------------------------------------------------------------------------- #
def test_cache_aller_retour(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache.C, "CACHE_DIR", tmp_path)
    df = _ohlcv()
    meta = cache.save(df, "SPY", "1d", "yahoo", "USD", adjusted=True)
    assert meta.rows == len(df)
    got, got_meta = cache.load("SPY", "1d")
    pd.testing.assert_frame_equal(got, df[cache.COLUMNS], check_freq=False)
    assert got_meta.provider == "yahoo" and got_meta.adjusted is True


def test_cache_refuse_une_serie_sans_metadonnee(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.C, "CACHE_DIR", tmp_path)
    cache.save(_ohlcv(), "SPY", "1d", "yahoo", "USD", True)
    (tmp_path / "SPY" / "1d.meta.json").unlink()
    assert cache.load("SPY", "1d") is None


def test_cache_refuse_colonnes_manquantes(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.C, "CACHE_DIR", tmp_path)
    with pytest.raises(ValueError, match="colonnes manquantes"):
        cache.save(_ohlcv().drop(columns=["adj_close"]), "SPY", "1d", "yahoo", "USD", True)


def test_cache_deduplique_et_trie(tmp_path, monkeypatch):
    monkeypatch.setattr(cache.C, "CACHE_DIR", tmp_path)
    df = _ohlcv(10)
    doubled = pd.concat([df, df.iloc[[-1]]])
    meta = cache.save(doubled.iloc[::-1], "SPY", "1d", "yahoo", "USD", True)
    got, _ = cache.load("SPY", "1d")
    assert meta.rows == 10
    assert got.index.is_monotonic_increasing and not got.index.duplicated().any()


# --------------------------------------------------------------------------- #
# Fournisseurs : refus explicites plutôt que données inventées
# --------------------------------------------------------------------------- #
def test_yahoo_refuse_lintraday():
    with pytest.raises(ProviderUnavailable, match="insuffisant pour les 3 ans"):
        YahooProvider().fetch("SPY", "5m", "2022-01-01")


def test_alpaca_sans_cle_est_indisponible(monkeypatch):
    monkeypatch.delenv("ALPACA_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    ok, reason = AlpacaProvider().available()
    assert not ok and "ALPACA_KEY_ID" in reason


def test_alpaca_refuse_les_titres_canadiens(monkeypatch):
    monkeypatch.setenv("ALPACA_KEY_ID", "x")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "y")
    with pytest.raises(ProviderUnavailable, match="canadiens"):
        AlpacaProvider().fetch("XIU.TO", "1d", "2023-01-01")


def test_ibkr_indisponible_sans_passerelle():
    ok, reason = IBKRProvider(port=1).available()
    assert not ok
    assert "ib_insync" in reason or "TWS" in reason


# --------------------------------------------------------------------------- #
# Pacing IBKR
# --------------------------------------------------------------------------- #
def test_pacer_laisse_passer_les_premieres_requetes():
    p = Pacer()
    assert p.delay_needed(0.0) == 0.0
    for t in range(5):
        p.acquire(now=float(t) * 0.5, sleep=lambda s: None)
    assert len(p.stamps) == 5


def test_pacer_bloque_au_dela_de_6_requetes_en_2s():
    p = Pacer()
    for k in range(6):
        p.acquire(now=k * 0.1, sleep=lambda s: None)
    assert p.delay_needed(0.7) > 0


def test_pacer_bloque_au_dela_de_60_requetes_en_10min():
    p = Pacer()
    for k in range(60):
        p.acquire(now=k * 3.0, sleep=lambda s: None)  # espacées, donc seule la règle 10 min joue
    assert p.delay_needed(180.0) > 0
    assert p.delay_needed(600.1) == 0.0


def test_pacer_oublie_les_requetes_de_plus_de_10_minutes():
    p = Pacer()
    for k in range(60):
        p.acquire(now=float(k), sleep=lambda s: None)
    p.delay_needed(700.0)
    assert len(p.stamps) == 0


def test_decoupage_des_requetes_historiques():
    chunks_5m = chunk_ranges("2023-01-01", "2023-04-01", "5m")
    assert len(chunks_5m) == 3          # 90 jours par tranches de 30
    assert chunks_5m[-1] == pd.Timestamp("2023-04-01").to_pydatetime()
    chunks_1d = chunk_ranges("2015-01-01", "2020-01-01", "1d")
    assert len(chunks_1d) == 6          # 5 ans par tranches de 1 an


# --------------------------------------------------------------------------- #
# Contrôles qualité
# --------------------------------------------------------------------------- #
def _checks(df, symbol="SPY", timeframe="1d"):
    return {f.check: f for f in quality.check_symbol(df, symbol, timeframe)}


def test_qc_detecte_ohlc_incoherent():
    df = _ohlcv(30)
    df.iloc[5, df.columns.get_loc("high")] = df["low"].iloc[5] * 0.5
    found = _checks(df)
    assert "ohlc_incoherent" in found and found["ohlc_incoherent"].blocking


def test_qc_detecte_volume_nul():
    df = _ohlcv(30)
    df.iloc[3, df.columns.get_loc("volume")] = 0
    assert "volume_nul" in _checks(df)


def test_qc_detecte_saut_suspect():
    df = _ohlcv(30)
    for col in ("open", "high", "low", "close"):
        df.iloc[10, df.columns.get_loc(col)] *= 2.0   # fractionnement non ajusté
    found = _checks(df)
    assert "saut_suspect" in found and not found["saut_suspect"].blocking


def test_qc_detecte_seances_manquantes():
    df = _ohlcv(60)
    troue = df.drop(df.index[10:25])
    found = _checks(troue)
    assert "seances_manquantes" in found and found["seances_manquantes"].blocking


def test_qc_serie_propre_ne_leve_rien_de_bloquant():
    df = _ohlcv(120)
    assert not any(f.blocking for f in quality.check_symbol(df, "SPY", "1d"))


def test_qc_serie_vide_est_bloquante():
    vide = pd.DataFrame(columns=cache.COLUMNS)
    assert _checks(vide)["vide"].blocking


# --------------------------------------------------------------------------- #
# Éligibilité à 200 $
# --------------------------------------------------------------------------- #
def test_eligibilite_rejette_un_titre_trop_cher():
    cher = _ohlcv(60, price=900.0)          # ~1230 $ CAD l'action
    table = universe.affordability({"SPY": cher}, cash_cad=200.0)
    assert table.iloc[0]["actions_pour_200cad"] == 0
    assert bool(table.iloc[0]["fractionnement_requis"]) is True
    assert bool(table.iloc[0]["tradable_actions_entieres"]) is False


def test_eligibilite_accepte_un_titre_bon_marche():
    pas_cher = _ohlcv(60, price=40.0)
    table = universe.affordability({"XLF": pas_cher}, cash_cad=200.0)
    row = table.iloc[0]
    assert row["actions_pour_200cad"] >= 3
    assert row["risque_1action_stop2pct_cad"] <= 5.0
    assert bool(row["tradable_actions_entieres"]) is True


def test_eligibilite_rejette_un_titre_illiquide():
    illiquide = _ohlcv(60, price=40.0)
    illiquide["volume"] = 100.0
    table = universe.affordability({"XYZ": illiquide}, cash_cad=200.0)
    assert bool(table.iloc[0]["liquide"]) is False
    assert bool(table.iloc[0]["tradable_actions_entieres"]) is False


def test_eligibilite_rejette_si_une_action_risque_plus_de_5_dollars():
    # 400 $ CAD l'action : un stop à 2 % coûte 8 $, au-dessus du plafond de 5 $.
    moyen = _ohlcv(60, price=292.0)   # ~400 $ CAD
    table = universe.affordability({"QQQ": moyen}, cash_cad=200.0)
    row = table.iloc[0]
    assert row["risque_1action_stop2pct_cad"] > 5.0
    assert bool(row["tradable_actions_entieres"]) is False


# --------------------------------------------------------------------------- #
# Événements macro
# --------------------------------------------------------------------------- #
FOMC_MEME_MOIS = "<p>January 27-28 Statement</p><p>March 17-18* Minutes</p>"
FOMC_A_CHEVAL = "<p>April 30-May 1 Statement</p>"
FOMC_ABREGE = "<p>Jan/Feb 31-1 Statement</p><p>Oct/Nov 31-1 Statement</p>"
FOMC_NOTE = "<p>January 26-27</p><p>Note: A two-day meeting is scheduled for January 25-26, 2028.</p>"


def test_fomc_meme_mois_prend_le_dernier_jour():
    dates = EV.parse_fomc_block(FOMC_MEME_MOIS, 2015)
    assert [str(d.date()) for d in dates] == ["2015-01-28", "2015-03-18"]


def test_fomc_a_cheval_sur_deux_mois():
    dates = EV.parse_fomc_block(FOMC_A_CHEVAL, 2024)
    assert [str(d.date()) for d in dates] == ["2024-05-01"]


def test_fomc_format_abrege():
    dates = EV.parse_fomc_block(FOMC_ABREGE, 2023)
    assert [str(d.date()) for d in dates] == ["2023-02-01", "2023-11-01"]


def test_fomc_ignore_une_note_qui_vise_une_autre_annee():
    dates = EV.parse_fomc_block(FOMC_NOTE, 2027)
    assert [str(d.date()) for d in dates] == ["2027-01-27"]


def test_fomc_ne_compte_pas_deux_fois_une_reunion_a_cheval():
    dates = EV.parse_fomc_block("<p>April 30-May 1</p>", 2024)
    assert len(dates) == 1


def test_evenements_ecrits_en_heure_de_new_york(tmp_path):
    ev = [EV.Event(pd.Timestamp("2024-05-01 14:00"), 60, "FOMC", "fed"),
          EV.Event(pd.Timestamp("2024-05-03 08:30"), 30, "EMPLOI", "bls")]
    path = tmp_path / "events.csv"
    EV.write_events_csv(ev, path, missing=["IPC : source injoignable"])
    text = path.read_text(encoding="utf-8")
    assert "# MANQUANT : IPC : source injoignable" in text
    assert "Heures de New York" in text
    df = pd.read_csv(path, comment="#")
    assert list(df.columns) == ["datetime", "window_min", "label"]
    assert df.iloc[0]["datetime"] == "2024-05-01 14:00"


def test_events_csv_relu_par_le_moteur_orb(tmp_path):
    """Le format doit rester lisible par `load_events` de run.py (parse + tz NY)."""
    ev = [EV.Event(pd.Timestamp("2024-05-01 14:00"), 60, "FOMC", "fed")]
    path = tmp_path / "events.csv"
    EV.write_events_csv(ev, path)
    df = pd.read_csv(path, comment="#")
    localized = pd.to_datetime(df["datetime"]).dt.tz_localize(C.TZ_NY)
    assert str(localized.iloc[0]) == "2024-05-01 14:00:00-04:00"


def test_bls_parse_une_ligne_de_calendrier():
    html = """<table><tr><td>Consumer Price Index for April 2024</td>
    <td>May 15, 2024</td><td>08:30 AM</td></tr>
    <tr><td>Employment Situation for April 2024</td><td>May 3, 2024</td></tr>
    <tr><td>Producer Price Index</td><td>May 14, 2024</td></tr></table>"""
    got = EV.parse_bls(html, 2024)
    assert (pd.Timestamp("2024-05-15"), "IPC") in got
    assert (pd.Timestamp("2024-05-03"), "EMPLOI") in got
    assert len(got) == 2  # l'IPP n'est pas retenu


# --------------------------------------------------------------------------- #
# Alpaca : choix du flux et ajustement
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = "" if status == 200 else "erreur simulée"

    def json(self):
        return self._payload


def _bars(n=3, close=100.0, offset=0):
    return [{"t": f"2024-01-{offset + k + 1:02d}T14:30:00Z", "o": close, "h": close + 1,
             "l": close - 1, "c": close, "v": 1000.0} for k in range(n)]


def test_alpaca_prefere_le_flux_consolide(monkeypatch):
    """SIP d'abord : IEX ne porte qu'une fraction du volume, inutilisable pour l'ORB."""
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    vus = []

    def fake_get(url, headers=None, params=None, timeout=None):
        vus.append(params["feed"])
        return _FakeResponse(200, {"bars": _bars(), "next_page_token": None})

    monkeypatch.setattr("data.providers.alpaca.requests.get", fake_get)
    provider = AlpacaProvider()
    provider.fetch("SPY", "5m", "2024-01-01")
    assert vus[0] == "sip"
    assert provider.last_feed == "sip"


def test_alpaca_bascule_sur_iex_si_sip_refuse(monkeypatch):
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    vus = []

    def fake_get(url, headers=None, params=None, timeout=None):
        vus.append(params["feed"])
        if params["feed"] == "sip":
            return _FakeResponse(403)
        return _FakeResponse(200, {"bars": _bars(), "next_page_token": None})

    monkeypatch.setattr("data.providers.alpaca.requests.get", fake_get)
    provider = AlpacaProvider()
    provider.fetch("SPY", "5m", "2024-01-01")
    assert vus == ["sip", "iex"]
    assert provider.last_feed == "iex"


def test_alpaca_leve_si_aucun_flux_ne_repond(monkeypatch):
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.setattr("data.providers.alpaca.requests.get",
                        lambda *a, **k: _FakeResponse(403))
    with pytest.raises(ProviderUnavailable, match="sip.*iex"):
        AlpacaProvider().fetch("SPY", "5m", "2024-01-01")


def test_alpaca_quotidien_garde_le_prix_brut_et_ajoute_lajuste(monkeypatch):
    """L'OHLC reste brut (il détermine le nombre d'actions et la commission) ;
    seul `adj_close` porte l'ajustement."""
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")

    def fake_get(url, headers=None, params=None, timeout=None):
        close = 100.0 if params["adjustment"] == "raw" else 96.0
        return _FakeResponse(200, {"bars": _bars(close=close), "next_page_token": None})

    monkeypatch.setattr("data.providers.alpaca.requests.get", fake_get)
    df = AlpacaProvider().fetch("SPY", "1d", "2024-01-01")
    assert (df["close"] == 100.0).all()
    assert (df["adj_close"] == 96.0).all()


def test_alpaca_intraday_ne_demande_pas_lajustement(monkeypatch):
    """En intraday, une seule requête : l'ajustement n'a pas de sens dans la journée."""
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    ajustements = []

    def fake_get(url, headers=None, params=None, timeout=None):
        ajustements.append(params["adjustment"])
        return _FakeResponse(200, {"bars": _bars(), "next_page_token": None})

    monkeypatch.setattr("data.providers.alpaca.requests.get", fake_get)
    AlpacaProvider().fetch("SPY", "5m", "2024-01-01")
    assert ajustements == ["raw"]


def test_alpaca_pagine_jusqua_epuisement(monkeypatch):
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    appels = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        appels["n"] += 1
        token = "suite" if appels["n"] < 3 else None
        # chaque page couvre des horodatages distincts, comme la vraie API
        return _FakeResponse(200, {"bars": _bars(offset=3 * (appels["n"] - 1)),
                                   "next_page_token": token})

    monkeypatch.setattr("data.providers.alpaca.requests.get", fake_get)
    df = AlpacaProvider().fetch("SPY", "5m", "2024-01-01")
    assert appels["n"] == 3
    assert len(df) == 9 and df.index.is_unique


def test_intraday_est_horodate_en_heure_de_new_york(monkeypatch):
    """Régression : `DatetimeIndex(series.values)` perd le fuseau et laisse
    des horodatages UTC déguisés en heure locale."""
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    # 14:30 UTC = 09:30 à New York (heure d'été), l'ouverture de la séance.
    bars = [{"t": "2024-06-03T13:30:00Z", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1.0}]
    monkeypatch.setattr("data.providers.alpaca.requests.get",
                        lambda *a, **k: _FakeResponse(200, {"bars": bars, "next_page_token": None}))
    df = AlpacaProvider().fetch("SPY", "5m", "2024-06-03")
    assert df.index.tz is not None, "l'index intraday doit porter un fuseau"
    assert str(df.index.tz) == C.TZ_NY
    assert df.index[0].strftime("%H:%M") == "09:30"


def test_quotidien_reste_sans_fuseau_et_normalise(monkeypatch):
    monkeypatch.setenv("ALPACA_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    bars = [{"t": "2024-06-03T04:00:00Z", "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0, "v": 1.0}]
    monkeypatch.setattr("data.providers.alpaca.requests.get",
                        lambda *a, **k: _FakeResponse(200, {"bars": bars, "next_page_token": None}))
    df = AlpacaProvider().fetch("SPY", "1d", "2024-06-03")
    assert df.index.tz is None
    assert str(df.index[0]) == "2024-06-03 00:00:00"


def test_qc_intraday_compte_les_barres_selon_lhoraire_reel():
    """Une séance complète fait 78 barres ; une demi-journée en fait 42 et ne
    doit pas être signalée comme incomplète."""
    pleine = pd.date_range("2024-06-03 09:30", "2024-06-03 15:55", freq="5min", tz=C.TZ_NY)
    demi = pd.date_range("2024-07-03 09:30", "2024-07-03 12:55", freq="5min", tz=C.TZ_NY)
    idx = pleine.append(demi)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                       "adj_close": 1.0, "volume": 1000.0}, index=idx)
    found = {f.check: f for f in quality.check_symbol(df, "SPY", "5m")}
    assert "seances_incompletes" not in found, found


def test_qc_intraday_signale_une_vraie_seance_trouee():
    pleine = pd.date_range("2024-06-03 09:30", "2024-06-03 15:55", freq="5min", tz=C.TZ_NY)
    trouee = pleine.delete(range(10, 40))   # 30 barres arrachées en pleine séance
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                       "adj_close": 1.0, "volume": 1000.0}, index=trouee)
    found = {f.check: f for f in quality.check_symbol(df, "SPY", "5m")}
    assert "seances_incompletes" in found and found["seances_incompletes"].blocking
