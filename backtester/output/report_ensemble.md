# Système de signaux par ensemble — rapport de validation

- Données : okx perps USDT, 1h, 2024-01-01 → 2026-09-21 (fenêtres de test concaténées)
- Univers point-in-time : top 30 par volume 30 j reconstruit chaque mois (45 rééquilibrages, 133 paires exploitables dans l'union)
- Configurations évaluées au total : **1760**

## Phase 1 — composantes isolées

Chaque composante est backtestée seule, sans filtre de régime, avec un sizing fixe à 2% pour que la comparaison soit à armes égales.

| strategie   | periode       |   trades |   sharpe | rendement_total   | max_drawdown   | win_rate   |   esperance_R |   profit_factor |   R_total |   duree_moyenne_h |
|:------------|:--------------|---------:|---------:|:------------------|:---------------|:-----------|--------------:|----------------:|----------:|------------------:|
| S1_tsmom    | complet       |      286 |    -0.07 | -26.8%            | -48.2%         | 36.4%      |         -0.03 |            0.89 |     -7.98 |            399.58 |
| S2_xsmom    | complet       |      433 |    -0.54 | -65.7%            | -73.2%         | 34.9%      |         -0.09 |            0.75 |    -40.46 |            358.05 |
| S3_donchian | complet       |      401 |    -0.64 | -68.1%            | -74.1%         | 27.2%      |         -0.12 |            0.71 |    -46.6  |            323.11 |
| S4_meanrev  | complet       |      735 |    -1.19 | -76.1%            | -79.7%         | 61.9%      |         -0.09 |            0.64 |    -63.5  |            177.62 |
| S1_tsmom    | in-sample     |      166 |    -0.09 | -17.8%            | -40.7%         | 36.7%      |         -0.02 |            0.9  |     -2.59 |            402.95 |
| S2_xsmom    | in-sample     |      240 |    -0.22 | -29.7%            | -52.5%         | 40.0%      |         -0.04 |            0.82 |     -8.83 |            337.97 |
| S3_donchian | in-sample     |      201 |    -0.42 | -37.4%            | -53.0%         | 27.9%      |         -0.08 |            0.74 |    -16.34 |            346.66 |
| S4_meanrev  | in-sample     |      422 |    -0.91 | -48.0%            | -57.0%         | 65.2%      |         -0.06 |            0.68 |    -27.24 |            158.49 |
| S1_tsmom    | out-of-sample |      127 |    -0.35 | -23.6%            | -39.2%         | 34.6%      |         -0.08 |            0.8  |    -10.28 |            357.92 |
| S2_xsmom    | out-of-sample |      190 |    -0.98 | -51.6%            | -64.1%         | 28.4%      |         -0.16 |            0.64 |    -30.27 |            378.72 |
| S3_donchian | out-of-sample |      200 |    -0.94 | -49.3%            | -59.0%         | 26.5%      |         -0.15 |            0.66 |    -30.11 |            295.11 |
| S4_meanrev  | out-of-sample |      312 |    -1.61 | -54.2%            | -60.1%         | 58.0%      |         -0.11 |            0.57 |    -35.01 |            198.76 |

### Matrice de corrélation des rendements quotidiens (période complète)

|             |   S1_tsmom |   S2_xsmom |   S3_donchian |   S4_meanrev |
|:------------|-----------:|-----------:|--------------:|-------------:|
| S1_tsmom    |       1    |       0.85 |          0.83 |         0.57 |
| S2_xsmom    |       0.85 |       1    |          0.83 |         0.7  |
| S3_donchian |       0.83 |       0.83 |          1    |         0.63 |
| S4_meanrev  |       0.57 |       0.7  |          0.63 |         1    |

### Application de la règle de sélection (Sharpe > 0.3 OOS, corrélation < 0.6)

- S1_tsmom: rejeté (Sharpe -0.35 <= 0.3)
- S3_donchian: rejeté (Sharpe -0.94 <= 0.3)
- S2_xsmom: rejeté (Sharpe -0.98 <= 0.3)
- S4_meanrev: rejeté (Sharpe -1.61 <= 0.3)

**Composantes retenues : AUCUNE**

## Phase 2 — ensemble et sizing

_Aucune composante retenue : pas d'ensemble à construire._

## Phase 3 — validation

### 3.1 Walk-forward glissant (train 12 mois / test 3 mois, pas 3 mois)

La sélection des composantes et du seuil est refaite **dans chaque fenêtre d'entraînement**, puis appliquée telle quelle aux 3 mois suivants. Les chiffres ci-dessous ne contiennent que des fenêtres de test.

| test                    |   SR S1 |   SR S2 |   SR S3 |   SR S4 | retenues   | seuil   |
|:------------------------|--------:|--------:|--------:|--------:|:-----------|:--------|
| 2024-01-01 → 2024-04-01 |    0.32 |   -0.29 |    0.07 |   -0.55 | S1_tsmom   | 0.30    |
| 2024-04-01 → 2024-07-01 |    0.49 |    0.14 |    0.46 |   -0.59 | S1_tsmom   | 0.30    |
| 2024-07-01 → 2024-10-01 |    0.27 |   -0.03 |   -0.02 |   -0.94 | aucune     | -       |
| 2024-10-01 → 2025-01-01 |    0.17 |    0.44 |   -0.18 |   -0.99 | S2_xsmom   | 0.50    |
| 2025-01-01 → 2025-04-01 |   -0.29 |    0.01 |   -0.74 |   -1.29 | aucune     | -       |
| 2025-04-01 → 2025-07-01 |   -0.7  |   -0.92 |   -2.06 |   -1.72 | aucune     | -       |
| 2025-07-01 → 2025-10-01 |   -0.24 |   -0.22 |   -0.95 |   -1.03 | aucune     | -       |
| 2025-10-01 → 2026-01-01 |    0.58 |    0.11 |   -0.33 |   -0.63 | S1_tsmom   | 0.70    |
| 2026-01-01 → 2026-04-01 |   -0.15 |   -0.3  |   -0.6  |   -1.58 | aucune     | -       |
| 2026-04-01 → 2026-07-01 |    0.27 |   -0.48 |   -0.02 |   -1.92 | aucune     | -       |
| 2026-07-01 → 2026-09-21 |   -0.21 |   -1.4  |   -0.81 |   -2.03 | aucune     | -       |

### 3.2 Benchmark

| strategie                          |   trades |   sharpe | rendement_total   | cagr   | vol_annualisee   | max_drawdown   |   calmar |
|:-----------------------------------|---------:|---------:|:------------------|:-------|:-----------------|:---------------|---------:|
| Ensemble (walk-forward, test only) |       44 |     0.52 | 45.0%             | 14.6%  | 34.7%            | -28.9%         |     0.51 |
| BTC buy & hold                     |        0 |     0.71 | 92.3%             | 27.2%  | 47.3%            | -53.8%         |     0.51 |

**Le système ne bat PAS BTC en Sharpe.**

### 3.2b Exposition réelle

Le Sharpe walk-forward doit se lire avec le temps réellement passé en marché : la plupart des folds ne retiennent aucune composante, donc le capital reste à plat.

| temps_en_position   |   mois_actifs |   mois_positifs |   meilleur_mois_pnl | part_du_meilleur_mois   |   pnl_total |
|:--------------------|--------------:|----------------:|--------------------:|:------------------------|------------:|
| 20.2%               |            10 |               6 |               24.52 | 55.6%                   |       44.09 |

### 3.3 Monte Carlo (1000 rééchantillonnages de la séquence de trades)

|   runs |   trades_par_run | rendement_p5   | rendement_median   | rendement_p95   | rendement_moyen   | maxdd_p5   | maxdd_median   | proba_perte   | proba_ruine_80pct   |
|-------:|-----------------:|:---------------|:-------------------|:----------------|:------------------|:-----------|:---------------|:--------------|:--------------------|
|   1000 |               44 | -20.9%         | 39.4%              | 175.4%          | 53.2%             | -36.8%     | -20.5%         | 18.1%         | 0.0%                |

### 3.4 Deflated Sharpe Ratio

Le DSR est la probabilité que le Sharpe observé soit supérieur à ce qu'on obtiendrait par pure chance compte tenu du nombre de configurations essayées. Un DSR proche de 1 valide, proche de 0 invalide.

|   sharpe_annualise |   sharpe_quotidien |   sharpe_seuil_hasard_annualise |   n_configurations |   variance_essais |   skewness |   kurtosis |   observations |   deflated_sharpe_ratio | comptage                       |
|-------------------:|-------------------:|--------------------------------:|-------------------:|------------------:|-----------:|-----------:|---------------:|------------------------:|:-------------------------------|
|               0.52 |               0.03 |                            1.63 |                 72 |                 0 |       1.58 |      29.93 |            994 |                    0.03 | configurations de sélection    |
|               0.52 |               0.03 |                            2.3  |               1688 |                 0 |       1.58 |      29.93 |            994 |                    0    | toutes configurations évaluées |

### 3.5 Sensibilité aux paramètres (±30%, Sharpe walk-forward)

| paramètre      |   -30% |   base |   +30% |
|:---------------|-------:|-------:|-------:|
| atr_stop_mult  |   0.8  |   0.52 |   0.46 |
| atr_trail_mult |   0.8  |   0.52 |   0.13 |
| vol_target     |   0.51 |   0.52 |   0.52 |
| max_risk       |   0.48 |   0.52 |   0.59 |
| max_corr       |  -0.21 |   0.52 |   0.36 |
| max_gross      |   0.78 |   0.52 |   0.51 |
| tsmom_horizons |   0.3  |   0.52 |   0.32 |
| xsmom_days     |   0.48 |   0.52 |   0.42 |
| donchian_fast  |   0.23 |   0.52 |   0.52 |
| donchian_slow  |   0.52 |   0.52 |   0.52 |
| meanrev_days   |   0.52 |   0.52 |   0.52 |
| er_bars        |   0.65 |   0.52 |   0.63 |

### 3.6 Sensibilité aux coûts

| strategie                 |   sharpe | rendement_total   | cagr   | vol_annualisee   | max_drawdown   |   calmar |   trades |
|:--------------------------|---------:|:------------------|:-------|:-----------------|:---------------|---------:|---------:|
| coûts nominaux            |     0.52 | 45.0%             | 14.6%  | 34.7%            | -28.9%         |     0.51 |       44 |
| frais et slippage doublés |     0.5  | 42.8%             | 14.0%  | 34.7%            | -29.0%         |     0.48 |       44 |

### Biais de survivance

| strategie                              |   sharpe | rendement_total   | cagr   | vol_annualisee   | max_drawdown   |   calmar |
|:---------------------------------------|---------:|:------------------|:-------|:-----------------|:---------------|---------:|
| univers point-in-time (top 30 mensuel) |     0.52 | 45.0%             | 14.6%  | 34.7%            | -28.9%         |     0.51 |
| univers figé (10 paires pré-2023)      |    -0.07 | -21.5%            | -8.5%  | 35.9%            | -49.2%         |    -0.17 |

## Réserves méthodologiques

1. **Paires délistées absentes.** L'univers point-in-time est reconstruit à partir des volumes quotidiens réels à chaque date, donc le *classement* est causal. Mais il ne peut contenir que des paires encore cotées aujourd'hui : celles délistées entre 2023 et 2026 sont invisibles. Le biais de survivance est réduit, pas éliminé.
2. **La règle de sélection de la phase 1 regarde l'out-of-sample.** C'est ce que demande la consigne, mais sélectionner sur la période de test est en soi une fuite. C'est pourquoi la phase 3 refait la sélection dans chaque fenêtre d'entraînement : seuls ces chiffres-là sont exploitables.
3. **Échantillon minuscule.** 44 trades hors échantillon sur 11 fenêtres. À ce volume, l'intervalle de confiance du Sharpe couvre largement zéro ; aucune des métriques n'a de puissance statistique.
4. **Le sizing vol-target ne mord jamais.** `20% / vol réalisée` dépasse le plafond de 5% dès que la vol annualisée est sous 400% — le cas de toutes les cryptos liquides. 98% des trades sont au plafond, donc le sizing « vol-target » est en pratique un sizing fixe à 5% et la comparaison avec le fixe 2% ne teste que le niveau de levier, pas l'adaptation à la volatilité.
5. **Exchange.** Bybit est géo-bloqué depuis l'environnement d'exécution ; le run tourne sur OKX avec le même code.

## Recommandation finale

| Critère | Verdict | Mesure |
|---|---|---|
| Phase 1 : au moins une composante passe Sharpe > 0.3 en OOS | NON | retenues : aucune (meilleur Sharpe OOS : -0.35) |
| Le système bat BTC buy & hold en Sharpe | NON | 0.52 contre 0.71 pour BTC |
| Deflated Sharpe Ratio > 0.95 | NON | DSR = 0.001 avec N = 1688 configurations (seuil de hasard : Sharpe 2.30) |
| Monte Carlo : 5e percentile du rendement positif | NON | p5 = -20.9%, P(perte) = 18% |
| Sensibilité : aucune perturbation ±30% ne fait passer le Sharpe sous 0 | NON | pire Sharpe observé -0.21 ; amplitude max 0.73 (paramètre le plus instable : max_corr) |
| Échantillon suffisant (>= 100 trades hors échantillon) | NON | 44 trades sur toutes les fenêtres de test |

**Recommandation : NE PAS DÉPLOYER** (0/6 critères remplis).

Les critères non remplis ne sont pas des détails de calibration : ils disent que l'edge mesuré n'est pas distinguable du bruit de sélection. Augmenter le nombre de configurations essayées ne ferait que dégrader davantage le DSR.

À noter : sur un univers figé de majors pré-2023, le même système donne un Sharpe de -0.07 contre 0.52 sur l'univers rotatif. La performance vient donc entièrement de la rotation vers les paires récemment devenues liquides, pas d'un edge sur les actifs établis.

## Graphiques

- `walkforward_equity.png`
- `correlation_matrix.png`
- `monte_carlo.png`
- `sensitivity.png`
