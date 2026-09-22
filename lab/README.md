# Laboratoire multi-stratégies (paper-first)

Le brief complet est dans `CLAUDE.md`. Phase courante : **A — Données (terminée, en attente de revue)**.

## Installation

    python -m venv .venv && .venv\Scripts\activate     # Windows
    pip install -r requirements.txt

## Phase A — collecte

    python -m data.fetch --daily      # quotidien 10 ans (IBKR > Alpaca > Yahoo)
    python -m data.fetch --intraday   # barres 5 min (IBKR ou Alpaca obligatoire)
    python -m data.fetch --events     # events.csv depuis Fed et BLS
    python -m data.fetch --all
    python -m pytest tests -q

Le rapport sort dans `reports/phase_a_donnees.md`.

## Sources

L'ordre de préférence est IBKR, puis Alpaca, puis Yahoo. Chaque série est mise en
cache avec un fichier `.meta.json` qui consigne la source, la date de
téléchargement et si les prix sont ajustés. Une série sans métadonnée est
refusée au chargement.

Pour utiliser IBKR : lancer TWS ou IB Gateway en **mode papier**, activer l'API
(port 7497 pour TWS, 4002 pour Gateway), puis `pip install ib_insync`.

Pour Alpaca : copier `.env.example` en `.env` et remplir `ALPACA_KEY_ID` et
`ALPACA_SECRET_KEY` (`.env` est dans `.gitignore`). Le fournisseur demande le
flux **SIP** (ruban consolidé) et ne retombe sur IEX que si le compte n'y a pas
droit ; le flux retenu est écrit dans les métadonnées du cache. L'écart est
majeur : sur SPY en 2024, IEX ne porte que 1,5 % du volume consolidé.

Alpaca ne couvre pas les FNB canadiens (`.TO`) : leurs barres 5 minutes
demandent IBKR.

## Structure

    data/        fournisseurs, cache parquet, contrôles qualité, événements macro
    reports/     rapports de phase
    tests/       pytest

`core/`, `strategies/`, `validation/` et `alerts/` arrivent aux phases B à E.
