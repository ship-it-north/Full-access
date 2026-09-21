# Backtester swing trading crypto

Backtest 1h sur perps USDT, règles de swing trading sur support/résistance,
frictions complètes, 2 variantes d'entrée × 3 niveaux de risque.

## Installation (Windows, Python 3.11+)

```bat
pip install -r requirements.txt
```

## Utilisation

```bat
python main.py                        :: Bybit, top 30 perps USDT, 6 combinaisons
python main.py --offline              :: rejoue depuis le cache parquet, sans réseau
python main.py --workers 4            :: téléchargement parallèle
python main.py --variant A --risk 0.02
python -m pytest tests -q             :: 41 tests
```

Sorties dans `output/` : `report.md`, `equity_curves.png`, `metrics_comparison.csv`,
`metrics_is_oos.csv`, `metrics_per_pair.csv`, `trades_all.csv` + un CSV par combinaison.
Cache OHLCV dans `data/*.parquet`.

## Structure

| Fichier | Rôle |
|---|---|
| `config.py` | tous les paramètres : règles, frictions, risque, univers |
| `data.py` | ccxt, sélection de l'univers, pagination, cache parquet |
| `rules.py` | fonctions pures : tendance, pivots, clusters, setup — testables |
| `backtest.py` | moteur événementiel : ordres, positions, frictions, sizing |
| `report.py` | métriques, tableaux, CSV, courbe d'équité |
| `main.py` | orchestration |
| `tests/` | tests synthétiques + vérifications de non-look-ahead sur données réelles |

## Règles implémentées

| Règle | Implémentation |
|---|---|
| Filtre de tendance | `close[i]/close[i-720]-1 ∈ [+30%, +100%]` **ET** `close > SMA(200)` |
| Pivot haut / bas | extremum **strict** sur 5 barres à gauche et 5 à droite |
| Confirmation pivot | utilisable seulement à partir de `index + 5` |
| Nouveau sommet B | `argmax(high[i-199:i])` avec `i - argmax < 30` |
| Supports | clusters des pivots bas des 500 dernières barres, écart < 1.0% |
| Niveau fort | ≥ 2 touches ; prix = moyenne du cluster |
| L1 / L2 | niveau fort le plus proche sous le close / le suivant en dessous |
| Entrée A | limite à L1, remplie si `low <= L1` |
| Entrée B | touche de L1, puis clôture haussière > L1 dans les 3 barres suivantes |
| Stop | `L2 × 0.997` |
| Skip | pas de L2 à moins de 15% sous L1 ; `(entrée-stop)/entrée > 8%` ; `R:R < 1.5` |
| Cible D | `entrée + (B - A)`, A = pivot bas confirmé précédant B |
| Breakeven | stop = entrée dès qu'une bougie **clôture** au-dessus de B |
| Time stop | sortie au close après 120 barres |
| Concurrence | 1 trade par paire, 5 positions simultanées max |

### Frictions

Maker 0.02% (entrée A, sortie sur cible), taker 0.055% (entrée B, stop, time stop),
funding 0.01% par 8h de détention (prorata), slippage 0.05% sur les sorties au stop.
**Stop et cible touchés dans la même bougie → compté comme une perte.**

## Points où la spec était ambiguë (décisions prises)

1. **Confirmation des pivots.** « plus haut sur 5 barres à gauche et 5 à droite,
   confirmé 5 barres plus tard » : un pivot en `i` n'est connaissable qu'après la
   clôture de `i+5`. Le moteur n'utilise donc un pivot qu'à partir de `i+5`.
2. **Point A.** Dernier pivot bas confirmé dont l'indice précède celui de B.
3. **Prix d'entrée variante B.** Clôture de la bougie de confirmation (ordre au
   marché → taker). La cible et le R:R sont recalculés à ce prix réel, pas à L1.
4. **Fenêtre de confirmation B.** Les 3 barres *suivant* la touche (la barre de
   touche elle-même ne compte pas).
5. **Durée de vie d'un ordre non exécuté** (`PENDING_EXPIRY_BARS = 30`). Non
   spécifié, mais nécessaire : une touche de L1 fait passer le prix sous L1, ce qui
   invalide temporairement le setup. Sans fenêtre de survie, la variante B ne
   pourrait jamais se déclencher. L'ordre meurt si le filtre de tendance casse ou
   après 30 barres.
6. **Levier maximal** (`MAX_LEVERAGE = 10`). Non spécifié ; garde-fou contre un
   notionnel absurde quand la distance au stop est minuscule. Le nombre de trades
   bridés est reporté (0 sur le run actuel, donc sans effet sur les résultats).
7. **Sélection quand plus de 5 signaux se présentent** : meilleur R:R d'abord,
   départage alphabétique.
8. **Funding** traité comme un coût systématique au prorata des barres détenues
   (la spec donne un taux unique, pas une série de funding réelle).
9. **Gaps.** Un stop ou une limite traversés à l'ouverture sont exécutés à
   l'ouverture si celle-ci est plus défavorable — jamais au niveau théorique.

## Vérification de l'absence de look-ahead

Quatre contrôles, tous automatisés :

1. **Invariance par préfixe** (`test_aucun_look_ahead_invariance_par_prefixe`,
   et sa version sur données réelles). On calcule les setups sur la série complète,
   puis sur la série tronquée à la barre N, et on compare barre par barre sur
   `[0, N)`. Si une fonction lisait le futur, tronquer changerait le résultat. Les
   setups sont identiques (L1, L2, stop, B, A).
2. **Rejeu incrémental** (`test_rejeu_incremental_identique`). Un backtest complet
   et un backtest sur les 70% premières barres produisent exactement les mêmes
   trades pour tous ceux clos avant la coupure (paire, dates, prix, raison).
3. **Causalité au niveau du moteur** (`test_entree_impossible_avant_la_barre_darmement`,
   `test_breakeven_ne_sapplique_pas_a_la_barre_qui_larme`, `test_causalite_des_trades`).
   Un setup détecté au close de la barre `i` ne peut être exécuté qu'à partir de
   `i+1` ; un breakeven armé au close de `i` ne protège qu'à partir de `i+1` ;
   tout prix d'entrée est contenu dans le range de sa bougie.
4. **Pivots jamais utilisés avant confirmation** (`test_pivot_jamais_utilise_avant_confirmation`) :
   pour chaque setup produit, `a_index + lag <= i` et `b_index <= i`.

Par construction, `rules.py` ne reçoit jamais que `bar_index` et ne lit aucun
indice supérieur ; le moteur traite chaque barre dans l'ordre gestion → exécution
→ armement, jamais l'inverse.

**Le seul biais résiduel n'est pas dans le moteur mais dans l'univers** :
les 30 paires sont sélectionnées sur le volume 24h *d'aujourd'hui*, donc
l'échantillon connaît les survivants. C'est ce que demande la spec, mais les
résultats sont optimistes de ce fait. Une correction propre demanderait un
classement de volume glissant reconstruit mois par mois.

## Résultats du run de référence

Exchange **OKX** (voir note ci-dessous), 29 paires, 1h, 2023-01-01 → 2026-09-21.

| Combinaison | Trades | Win rate | R moyen | Profit factor | Rendement | Max DD | Série perdante |
|---|---:|---:|---:|---:|---:|---:|---:|
| A – risque 2% | 216 | 26.4% | −0.01 | 0.94 | −17.5% | −52.0% | 17 |
| A – risque 5% | 216 | 26.4% | −0.01 | 0.91 | −63.1% | −86.6% | 17 |
| A – risque 10% | 216 | 26.4% | −0.01 | 0.87 | −97.3% | −99.0% | 17 |
| B – risque 2% | 93 | 22.6% | −0.24 | 0.65 | −38.4% | −43.0% | 13 |
| B – risque 5% | 93 | 22.6% | −0.24 | 0.64 | −74.2% | −76.7% | 13 |
| B – risque 10% | 93 | 22.6% | −0.24 | 0.62 | −95.8% | −96.5% | 13 |

Split IS/OOS (variante A) : **in-sample 2023-2024 = +0.16 R/trade**,
**out-of-sample 2025-2026 = −0.23 R/trade**. L'edge apparent disparaît hors
échantillon. Le risque par trade ne change pas l'espérance en R (mêmes trades),
seulement la vitesse de destruction du capital : à 10%, ruine quasi complète.

### Note sur l'exchange du run

Bybit (et Binance) sont géo-bloqués depuis l'environnement où ce run a été exécuté
(CloudFront renvoie 403). Le run de référence a donc tourné sur **OKX**, même code,
mêmes règles. Sur votre machine Windows, `python main.py` utilise **Bybit** par
défaut, comme demandé. Les perps d'actifs tokenisés non-crypto présents chez OKX
(or, pétrole, actions) sont exclus via `NON_CRYPTO_BASES`.

### Limites connues

- La courbe d'équité est construite sur les trades **clos** (pas de mark-to-market
  des positions ouvertes) : le max drawdown réel intra-trade est plus profond.
- Funding modélisé comme un coût fixe, pas comme la série historique réelle.
- Pas de contrainte de liquidité ni de taille minimale d'ordre ; avec 100$ de
  capital certaines tailles seraient sous le minimum d'échange réel.
- Stratégie 100% long : les 5 positions simultanées sont fortement corrélées, ce
  que montre le décrochage groupé de mai 2025.
