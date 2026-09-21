# Backtest swing crypto — rapport

- Exchange : **okx** (perps USDT, marché `swap`)
- Timeframe : 1h — période couverte : 2023-01-01 → 2026-09-21
- Univers : 29 paires
- Capital initial : 100 $ — risque par trade : 2%, 5%, 10%
- Frictions : maker 0.020%, taker 0.055%, funding 0.01%/8h, slippage stop 0.05%

## Comparatif des 6 combinaisons

| combinaison   |   trades | win_rate   |   R_moyen |   esperance_R |   R_moyen_gagnant |   R_moyen_perdant |   profit_factor | rendement_total   |   capital_final | max_drawdown   |   serie_perdante_max |   duree_moyenne_h |   trades_bridés |
|:--------------|---------:|:-----------|----------:|--------------:|------------------:|------------------:|----------------:|:------------------|----------------:|:---------------|---------------------:|------------------:|----------------:|
| A-risk2%      |      216 | 26.4%      |     -0.01 |         -0.01 |              2.63 |             -0.96 |            0.94 | -17.5%            |           82.46 | -52.0%         |                   17 |             25.05 |               0 |
| A-risk5%      |      216 | 26.4%      |     -0.01 |         -0.01 |              2.63 |             -0.96 |            0.91 | -63.1%            |           36.88 | -86.6%         |                   17 |             25.05 |               0 |
| A-risk10%     |      216 | 26.4%      |     -0.01 |         -0.01 |              2.63 |             -0.96 |            0.87 | -97.3%            |            2.7  | -99.0%         |                   17 |             25.05 |               0 |
| B-risk2%      |       93 | 22.6%      |     -0.24 |         -0.24 |              2.04 |             -0.91 |            0.65 | -38.4%            |           61.55 | -43.0%         |                   13 |             29.06 |               0 |
| B-risk5%      |       93 | 22.6%      |     -0.24 |         -0.24 |              2.04 |             -0.91 |            0.64 | -74.2%            |           25.81 | -76.7%         |                   13 |             29.06 |               0 |
| B-risk10%     |       93 | 22.6%      |     -0.24 |         -0.24 |              2.04 |             -0.91 |            0.62 | -95.8%            |            4.19 | -96.5%         |                   13 |             29.06 |               0 |

## Split in-sample / out-of-sample

| combinaison   | periode       |   trades | win_rate   |   R_moyen |   esperance_R |   R_moyen_gagnant |   R_moyen_perdant |   profit_factor | rendement_total   |   capital_final | max_drawdown   |   serie_perdante_max |   duree_moyenne_h |   trades_bridés |
|:--------------|:--------------|---------:|:-----------|----------:|--------------:|------------------:|------------------:|----------------:|:------------------|----------------:|:---------------|---------------------:|------------------:|----------------:|
| A-risk2%      | in-sample     |      123 | 31.7%      |      0.16 |          0.16 |              2.57 |             -0.96 |            1.21 | 35.3%             |          135.27 | -24.4%         |                   12 |             27.27 |               0 |
| A-risk2%      | out-of-sample |       93 | 19.4%      |     -0.23 |         -0.23 |              2.74 |             -0.95 |            0.62 | -39.0%            |           82.46 | -48.2%         |                   17 |             22.12 |               0 |
| A-risk5%      | in-sample     |      123 | 31.7%      |      0.16 |          0.16 |              2.57 |             -0.96 |            1.14 | 57.4%             |          157.44 | -51.0%         |                   12 |             27.27 |               0 |
| A-risk5%      | out-of-sample |       93 | 19.4%      |     -0.23 |         -0.23 |              2.74 |             -0.95 |            0.53 | -76.6%            |           36.88 | -83.4%         |                   17 |             22.12 |               0 |
| A-risk10%     | in-sample     |      123 | 31.7%      |      0.16 |          0.16 |              2.57 |             -0.96 |            1    | 0.3%              |          100.33 | -77.3%         |                   12 |             27.27 |               0 |
| A-risk10%     | out-of-sample |       93 | 19.4%      |     -0.23 |         -0.23 |              2.74 |             -0.95 |            0.44 | -97.3%            |            2.7  | -98.4%         |                   17 |             22.12 |               0 |
| B-risk2%      | in-sample     |       48 | 29.2%      |      0.01 |          0.01 |              2.15 |             -0.87 |            0.98 | -1.3%             |           98.75 | -13.9%         |                    6 |             33.08 |               0 |
| B-risk2%      | out-of-sample |       45 | 15.6%      |     -0.51 |         -0.51 |              1.83 |             -0.94 |            0.31 | -37.7%            |           61.55 | -40.4%         |                   10 |             24.78 |               0 |
| B-risk5%      | in-sample     |       48 | 29.2%      |      0.01 |          0.01 |              2.15 |             -0.87 |            0.91 | -10.7%            |           89.33 | -34.7%         |                    6 |             33.08 |               0 |
| B-risk5%      | out-of-sample |       45 | 15.6%      |     -0.51 |         -0.51 |              1.83 |             -0.94 |            0.25 | -71.1%            |           25.81 | -73.9%         |                   10 |             24.78 |               0 |
| B-risk10%     | in-sample     |       48 | 29.2%      |      0.01 |          0.01 |              2.15 |             -0.87 |            0.79 | -38.4%            |           61.58 | -64.1%         |                    6 |             33.08 |               0 |
| B-risk10%     | out-of-sample |       45 | 15.6%      |     -0.51 |         -0.51 |              1.83 |             -0.94 |            0.16 | -93.2%            |            4.19 | -94.3%         |                   10 |             24.78 |               0 |

## Raisons de sortie

| combinaison   |   stop |   target |   breakeven_stop |   time_stop |   stop_and_target_same_bar |
|:--------------|-------:|---------:|-----------------:|------------:|---------------------------:|
| A-risk2%      |    144 |       49 |               14 |           8 |                          1 |
| A-risk5%      |    144 |       49 |               14 |           8 |                          1 |
| A-risk10%     |    144 |       49 |               14 |           8 |                          1 |
| B-risk2%      |     62 |       18 |               10 |           3 |                          0 |
| B-risk5%      |     62 |       18 |               10 |           3 |                          0 |
| B-risk10%     |     62 |       18 |               10 |           3 |                          0 |

## Décomposition par paire

| combinaison   | paire            |   trades | win_rate   |   R_total |   R_moyen |   pnl_net |
|:--------------|:-----------------|---------:|:-----------|----------:|----------:|----------:|
| A-risk10%     | FIL_USDT_USDT    |        6 | 50.0%      |     11.05 |      1.84 |     34.71 |
| A-risk10%     | WLD_USDT_USDT    |        7 | 42.9%      |      9.04 |      1.29 |     69.23 |
| A-risk10%     | INJ_USDT_USDT    |        5 | 60.0%      |      5.71 |      1.14 |      5.85 |
| A-risk10%     | BCH_USDT_USDT    |        7 | 28.6%      |      4.09 |      0.58 |     15.77 |
| A-risk10%     | ENS_USDT_USDT    |       15 | 20.0%      |      3.53 |      0.24 |     18.78 |
| A-risk10%     | SOL_USDT_USDT    |       12 | 33.3%      |      3.38 |      0.28 |     -4.67 |
| A-risk10%     | SUI_USDT_USDT    |       21 | 33.3%      |      1.88 |      0.09 |      9.63 |
| A-risk10%     | ZEN_USDT_USDT    |        1 | 100.0%     |      1.87 |      1.87 |      0.57 |
| A-risk10%     | YFI_USDT_USDT    |        6 | 50.0%      |      1.13 |      0.19 |     15.8  |
| A-risk10%     | AR_USDT_USDT     |       11 | 45.5%      |      0.88 |      0.08 |    -14.67 |
| A-risk10%     | OKB_USDT_USDT    |        2 | 50.0%      |      0.2  |      0.1  |     -0.04 |
| A-risk10%     | HYPE_USDT_USDT   |        5 | 20.0%      |     -0.04 |     -0.01 |    -10.8  |
| A-risk10%     | LINK_USDT_USDT   |       10 | 30.0%      |     -0.23 |     -0.02 |    -11.72 |
| A-risk10%     | BTC_USDT_USDT    |        6 | 33.3%      |     -0.25 |     -0.04 |    -22.63 |
| A-risk10%     | STRK_USDT_USDT   |        3 | 33.3%      |     -0.32 |     -0.11 |      2.2  |
| A-risk10%     | TRUMP_USDT_USDT  |        6 | 16.7%      |     -0.92 |     -0.15 |    -10.87 |
| A-risk10%     | LIT_USDT_USDT    |        5 | 20.0%      |     -0.96 |     -0.19 |     -0.56 |
| A-risk10%     | AVAX_USDT_USDT   |        9 | 33.3%      |     -1.02 |     -0.11 |     -6.35 |
| A-risk10%     | VVV_USDT_USDT    |        1 | 0.0%       |     -1.05 |     -1.05 |     -0.21 |
| A-risk10%     | DASH_USDT_USDT   |        5 | 20.0%      |     -1.44 |     -0.29 |     -0.76 |
| A-risk10%     | AAVE_USDT_USDT   |       15 | 20.0%      |     -2.91 |     -0.19 |    -25.18 |
| A-risk10%     | ICP_USDT_USDT    |        8 | 12.5%      |     -3.47 |     -0.43 |    -35.65 |
| A-risk10%     | UNI_USDT_USDT    |       11 | 18.2%      |     -4    |     -0.36 |    -54.38 |
| A-risk10%     | ZEC_USDT_USDT    |        5 | 0.0%       |     -4.22 |     -0.84 |     -1.69 |
| A-risk10%     | TAO_USDT_USDT    |        6 | 16.7%      |     -5.11 |     -0.85 |     -5.07 |
| A-risk10%     | ETH_USDT_USDT    |        9 | 11.1%      |     -5.73 |     -0.64 |     -7.83 |
| A-risk10%     | ORDI_USDT_USDT   |       12 | 8.3%       |     -6.06 |     -0.5  |    -54.06 |
| A-risk10%     | GIGGLE_USDT_USDT |        7 | 0.0%       |     -7.25 |     -1.04 |     -2.69 |
| A-risk2%      | FIL_USDT_USDT    |        6 | 50.0%      |     11.05 |      1.84 |     19.09 |
| A-risk2%      | WLD_USDT_USDT    |        7 | 42.9%      |      9.04 |      1.29 |     20.83 |
| A-risk2%      | INJ_USDT_USDT    |        5 | 60.0%      |      5.71 |      1.14 |      9.93 |
| A-risk2%      | BCH_USDT_USDT    |        7 | 28.6%      |      4.09 |      0.58 |      8.6  |
| A-risk2%      | ENS_USDT_USDT    |       15 | 20.0%      |      3.53 |      0.24 |      6.22 |
| A-risk2%      | SOL_USDT_USDT    |       12 | 33.3%      |      3.38 |      0.28 |      3.66 |
| A-risk2%      | SUI_USDT_USDT    |       21 | 33.3%      |      1.88 |      0.09 |      0.52 |
| A-risk2%      | ZEN_USDT_USDT    |        1 | 100.0%     |      1.87 |      1.87 |      3.1  |
| A-risk2%      | YFI_USDT_USDT    |        6 | 50.0%      |      1.13 |      0.19 |      4.47 |
| A-risk2%      | AR_USDT_USDT     |       11 | 45.5%      |      0.88 |      0.08 |     -1.14 |
| A-risk2%      | OKB_USDT_USDT    |        2 | 50.0%      |      0.2  |      0.1  |      0.2  |
| A-risk2%      | HYPE_USDT_USDT   |        5 | 20.0%      |     -0.04 |     -0.01 |     -1.65 |
| A-risk2%      | LINK_USDT_USDT   |       10 | 30.0%      |     -0.23 |     -0.02 |     -0.06 |
| A-risk2%      | BTC_USDT_USDT    |        6 | 33.3%      |     -0.25 |     -0.04 |     -1.28 |
| A-risk2%      | STRK_USDT_USDT   |        3 | 33.3%      |     -0.32 |     -0.11 |     -0.78 |
| A-risk2%      | TRUMP_USDT_USDT  |        6 | 16.7%      |     -0.92 |     -0.15 |     -2.65 |
| A-risk2%      | LIT_USDT_USDT    |        5 | 20.0%      |     -0.96 |     -0.19 |     -1.91 |
| A-risk2%      | AVAX_USDT_USDT   |        9 | 33.3%      |     -1.02 |     -0.11 |     -3.17 |
| A-risk2%      | VVV_USDT_USDT    |        1 | 0.0%       |     -1.05 |     -1.05 |     -1.59 |
| A-risk2%      | DASH_USDT_USDT   |        5 | 20.0%      |     -1.44 |     -0.29 |     -2.73 |
| A-risk2%      | AAVE_USDT_USDT   |       15 | 20.0%      |     -2.91 |     -0.19 |     -6.24 |
| A-risk2%      | ICP_USDT_USDT    |        8 | 12.5%      |     -3.47 |     -0.43 |     -7.78 |
| A-risk2%      | UNI_USDT_USDT    |       11 | 18.2%      |     -4    |     -0.36 |    -10.58 |
| A-risk2%      | ZEC_USDT_USDT    |        5 | 0.0%       |     -4.22 |     -0.84 |     -6.99 |
| A-risk2%      | TAO_USDT_USDT    |        6 | 16.7%      |     -5.11 |     -0.85 |     -9.33 |
| A-risk2%      | ETH_USDT_USDT    |        9 | 11.1%      |     -5.73 |     -0.64 |    -10.58 |
| A-risk2%      | ORDI_USDT_USDT   |       12 | 8.3%       |     -6.06 |     -0.5  |    -14.02 |
| A-risk2%      | GIGGLE_USDT_USDT |        7 | 0.0%       |     -7.25 |     -1.04 |    -11.69 |
| A-risk5%      | FIL_USDT_USDT    |        6 | 50.0%      |     11.05 |      1.84 |     35.68 |
| A-risk5%      | WLD_USDT_USDT    |        7 | 42.9%      |      9.04 |      1.29 |     53.75 |
| A-risk5%      | INJ_USDT_USDT    |        5 | 60.0%      |      5.71 |      1.14 |     14.17 |
| A-risk5%      | BCH_USDT_USDT    |        7 | 28.6%      |      4.09 |      0.58 |     18.64 |
| A-risk5%      | ENS_USDT_USDT    |       15 | 20.0%      |      3.53 |      0.24 |     12.61 |
| A-risk5%      | SOL_USDT_USDT    |       12 | 33.3%      |      3.38 |      0.28 |      0.54 |
| A-risk5%      | SUI_USDT_USDT    |       21 | 33.3%      |      1.88 |      0.09 |     -1.98 |
| A-risk5%      | ZEN_USDT_USDT    |        1 | 100.0%     |      1.87 |      1.87 |      3.56 |
| A-risk5%      | YFI_USDT_USDT    |        6 | 50.0%      |      1.13 |      0.19 |     14.39 |
| A-risk5%      | AR_USDT_USDT     |       11 | 45.5%      |      0.88 |      0.08 |     -9.87 |
| A-risk5%      | OKB_USDT_USDT    |        2 | 50.0%      |      0.2  |      0.1  |      0.04 |
| A-risk5%      | HYPE_USDT_USDT   |        5 | 20.0%      |     -0.04 |     -0.01 |     -7.87 |
| A-risk5%      | LINK_USDT_USDT   |       10 | 30.0%      |     -0.23 |     -0.02 |     -2.41 |
| A-risk5%      | BTC_USDT_USDT    |        6 | 33.3%      |     -0.25 |     -0.04 |     -7.37 |
| A-risk5%      | STRK_USDT_USDT   |        3 | 33.3%      |     -0.32 |     -0.11 |     -1.26 |
| A-risk5%      | TRUMP_USDT_USDT  |        6 | 16.7%      |     -0.92 |     -0.15 |     -8.13 |
| A-risk5%      | LIT_USDT_USDT    |        5 | 20.0%      |     -0.96 |     -0.19 |     -2.69 |
| A-risk5%      | AVAX_USDT_USDT   |        9 | 33.3%      |     -1.02 |     -0.11 |     -7.78 |
| A-risk5%      | VVV_USDT_USDT    |        1 | 0.0%       |     -1.05 |     -1.05 |     -1.61 |
| A-risk5%      | DASH_USDT_USDT   |        5 | 20.0%      |     -1.44 |     -0.29 |     -3.7  |
| A-risk5%      | AAVE_USDT_USDT   |       15 | 20.0%      |     -2.91 |     -0.19 |    -16.11 |
| A-risk5%      | ICP_USDT_USDT    |        8 | 12.5%      |     -3.47 |     -0.43 |    -21.39 |
| A-risk5%      | UNI_USDT_USDT    |       11 | 18.2%      |     -4    |     -0.36 |    -32.99 |
| A-risk5%      | ZEC_USDT_USDT    |        5 | 0.0%       |     -4.22 |     -0.84 |     -8.46 |
| A-risk5%      | TAO_USDT_USDT    |        6 | 16.7%      |     -5.11 |     -0.85 |    -14.01 |
| A-risk5%      | ETH_USDT_USDT    |        9 | 11.1%      |     -5.73 |     -0.64 |    -17.06 |
| A-risk5%      | ORDI_USDT_USDT   |       12 | 8.3%       |     -6.06 |     -0.5  |    -38.08 |
| A-risk5%      | GIGGLE_USDT_USDT |        7 | 0.0%       |     -7.25 |     -1.04 |    -13.72 |
| B-risk10%     | SOL_USDT_USDT    |        6 | 50.0%      |      4    |      0.67 |     19.29 |
| B-risk10%     | FIL_USDT_USDT    |        4 | 50.0%      |      2.29 |      0.57 |      7.73 |
| B-risk10%     | BCH_USDT_USDT    |        3 | 33.3%      |      1.95 |      0.65 |      6.63 |
| B-risk10%     | ZEN_USDT_USDT    |        1 | 100.0%     |      1.84 |      1.84 |      0.7  |
| B-risk10%     | LIT_USDT_USDT    |        2 | 50.0%      |      1.76 |      0.88 |      0.72 |
| B-risk10%     | LINK_USDT_USDT   |        4 | 50.0%      |      0.93 |      0.23 |      3.06 |
| B-risk10%     | AVAX_USDT_USDT   |        2 | 50.0%      |      0.82 |      0.41 |      7.93 |
| B-risk10%     | OKB_USDT_USDT    |        1 | 100.0%     |      0.68 |      0.68 |      0.27 |
| B-risk10%     | TRUMP_USDT_USDT  |        3 | 33.3%      |      0.09 |      0.03 |     -3.78 |
| B-risk10%     | UNI_USDT_USDT    |        4 | 25.0%      |     -0.26 |     -0.07 |     -2.58 |
| B-risk10%     | INJ_USDT_USDT    |        3 | 33.3%      |     -0.36 |     -0.12 |     -5.56 |
| B-risk10%     | WLD_USDT_USDT    |        5 | 20.0%      |     -0.66 |     -0.13 |     -6.3  |
| B-risk10%     | YFI_USDT_USDT    |        2 | 50.0%      |     -0.78 |     -0.39 |     -2.53 |
| B-risk10%     | DASH_USDT_USDT   |        2 | 0.0%       |     -1.05 |     -0.53 |     -0.7  |
| B-risk10%     | ICP_USDT_USDT    |        2 | 0.0%       |     -1.11 |     -0.56 |     -8.53 |
| B-risk10%     | ETH_USDT_USDT    |        5 | 20.0%      |     -1.24 |     -0.25 |     -7.72 |
| B-risk10%     | TAO_USDT_USDT    |        2 | 0.0%       |     -2.07 |     -1.04 |     -2.06 |
| B-risk10%     | HYPE_USDT_USDT   |        2 | 0.0%       |     -2.08 |     -1.04 |     -5.66 |
| B-risk10%     | BTC_USDT_USDT    |        2 | 0.0%       |     -2.16 |     -1.08 |    -19.2  |
| B-risk10%     | AAVE_USDT_USDT   |       10 | 20.0%      |     -2.45 |     -0.24 |    -17.66 |
| B-risk10%     | GIGGLE_USDT_USDT |        3 | 0.0%       |     -3.11 |     -1.04 |     -2.16 |
| B-risk10%     | ORDI_USDT_USDT   |        3 | 0.0%       |     -3.13 |     -1.04 |    -14.41 |
| B-risk10%     | ZEC_USDT_USDT    |        3 | 0.0%       |     -3.14 |     -1.05 |     -1.97 |
| B-risk10%     | AR_USDT_USDT     |        4 | 0.0%       |     -3.15 |     -0.79 |    -10.64 |
| B-risk10%     | ENS_USDT_USDT    |        6 | 0.0%       |     -4.29 |     -0.71 |     -8.59 |
| B-risk10%     | SUI_USDT_USDT    |        9 | 11.1%      |     -5.65 |     -0.63 |    -22.1  |
| B-risk2%      | SOL_USDT_USDT    |        6 | 50.0%      |      4    |      0.67 |      6.99 |
| B-risk2%      | FIL_USDT_USDT    |        4 | 50.0%      |      2.29 |      0.57 |      3.82 |
| B-risk2%      | BCH_USDT_USDT    |        3 | 33.3%      |      1.95 |      0.65 |      3.29 |
| B-risk2%      | ZEN_USDT_USDT    |        1 | 100.0%     |      1.84 |      1.84 |      2.2  |
| B-risk2%      | LIT_USDT_USDT    |        2 | 50.0%      |      1.76 |      0.88 |      2.09 |
| B-risk2%      | LINK_USDT_USDT   |        4 | 50.0%      |      0.93 |      0.23 |      1.67 |
| B-risk2%      | AVAX_USDT_USDT   |        2 | 50.0%      |      0.82 |      0.41 |      1.74 |
| B-risk2%      | OKB_USDT_USDT    |        1 | 100.0%     |      0.68 |      0.68 |      0.82 |
| B-risk2%      | TRUMP_USDT_USDT  |        3 | 33.3%      |      0.09 |      0.03 |     -0.24 |
| B-risk2%      | UNI_USDT_USDT    |        4 | 25.0%      |     -0.26 |     -0.07 |     -0.57 |
| B-risk2%      | INJ_USDT_USDT    |        3 | 33.3%      |     -0.36 |     -0.12 |     -1.02 |
| B-risk2%      | WLD_USDT_USDT    |        5 | 20.0%      |     -0.66 |     -0.13 |     -1.34 |
| B-risk2%      | YFI_USDT_USDT    |        2 | 50.0%      |     -0.78 |     -0.39 |     -1.45 |
| B-risk2%      | DASH_USDT_USDT   |        2 | 0.0%       |     -1.05 |     -0.53 |     -1.39 |
| B-risk2%      | ICP_USDT_USDT    |        2 | 0.0%       |     -1.11 |     -0.56 |     -2.27 |
| B-risk2%      | ETH_USDT_USDT    |        5 | 20.0%      |     -1.24 |     -0.25 |     -2.07 |
| B-risk2%      | TAO_USDT_USDT    |        2 | 0.0%       |     -2.07 |     -1.04 |     -2.94 |
| B-risk2%      | HYPE_USDT_USDT   |        2 | 0.0%       |     -2.08 |     -1.04 |     -3.26 |
| B-risk2%      | BTC_USDT_USDT    |        2 | 0.0%       |     -2.16 |     -1.08 |     -4.38 |
| B-risk2%      | AAVE_USDT_USDT   |       10 | 20.0%      |     -2.45 |     -0.24 |     -4.36 |
| B-risk2%      | GIGGLE_USDT_USDT |        3 | 0.0%       |     -3.11 |     -1.04 |     -4.1  |
| B-risk2%      | ORDI_USDT_USDT   |        3 | 0.0%       |     -3.13 |     -1.04 |     -5.47 |
| B-risk2%      | ZEC_USDT_USDT    |        3 | 0.0%       |     -3.14 |     -1.05 |     -4.09 |
| B-risk2%      | AR_USDT_USDT     |        4 | 0.0%       |     -3.15 |     -0.79 |     -5.27 |
| B-risk2%      | ENS_USDT_USDT    |        6 | 0.0%       |     -4.29 |     -0.71 |     -6.89 |
| B-risk2%      | SUI_USDT_USDT    |        9 | 11.1%      |     -5.65 |     -0.63 |     -9.93 |
| B-risk5%      | SOL_USDT_USDT    |        6 | 50.0%      |      4    |      0.67 |     14.14 |
| B-risk5%      | FIL_USDT_USDT    |        4 | 50.0%      |      2.29 |      0.57 |      7.07 |
| B-risk5%      | BCH_USDT_USDT    |        3 | 33.3%      |      1.95 |      0.65 |      6.11 |
| B-risk5%      | ZEN_USDT_USDT    |        1 | 100.0%     |      1.84 |      1.84 |      2.22 |
| B-risk5%      | LIT_USDT_USDT    |        2 | 50.0%      |      1.76 |      0.88 |      2.14 |
| B-risk5%      | LINK_USDT_USDT   |        4 | 50.0%      |      0.93 |      0.23 |      3.19 |
| B-risk5%      | AVAX_USDT_USDT   |        2 | 50.0%      |      0.82 |      0.41 |      4.5  |
| B-risk5%      | OKB_USDT_USDT    |        1 | 100.0%     |      0.68 |      0.68 |      0.84 |
| B-risk5%      | TRUMP_USDT_USDT  |        3 | 33.3%      |      0.09 |      0.03 |     -1.63 |
| B-risk5%      | UNI_USDT_USDT    |        4 | 25.0%      |     -0.26 |     -0.07 |     -1.48 |
| B-risk5%      | INJ_USDT_USDT    |        3 | 33.3%      |     -0.36 |     -0.12 |     -3.06 |
| B-risk5%      | WLD_USDT_USDT    |        5 | 20.0%      |     -0.66 |     -0.13 |     -3.38 |
| B-risk5%      | YFI_USDT_USDT    |        2 | 50.0%      |     -0.78 |     -0.39 |     -2.87 |
| B-risk5%      | DASH_USDT_USDT   |        2 | 0.0%       |     -1.05 |     -0.53 |     -1.66 |
| B-risk5%      | ICP_USDT_USDT    |        2 | 0.0%       |     -1.11 |     -0.56 |     -5.47 |
| B-risk5%      | ETH_USDT_USDT    |        5 | 20.0%      |     -1.24 |     -0.25 |     -4.16 |
| B-risk5%      | TAO_USDT_USDT    |        2 | 0.0%       |     -2.07 |     -1.04 |     -3.93 |
| B-risk5%      | HYPE_USDT_USDT   |        2 | 0.0%       |     -2.08 |     -1.04 |     -5.58 |
| B-risk5%      | BTC_USDT_USDT    |        2 | 0.0%       |     -2.16 |     -1.08 |    -10.79 |
| B-risk5%      | AAVE_USDT_USDT   |       10 | 20.0%      |     -2.45 |     -0.24 |     -9.62 |
| B-risk5%      | GIGGLE_USDT_USDT |        3 | 0.0%       |     -3.11 |     -1.04 |     -4.9  |
| B-risk5%      | ORDI_USDT_USDT   |        3 | 0.0%       |     -3.13 |     -1.04 |    -10.88 |
| B-risk5%      | ZEC_USDT_USDT    |        3 | 0.0%       |     -3.14 |     -1.05 |     -4.78 |
| B-risk5%      | AR_USDT_USDT     |        4 | 0.0%       |     -3.15 |     -0.79 |     -9.67 |
| B-risk5%      | ENS_USDT_USDT    |        6 | 0.0%       |     -4.29 |     -0.71 |    -11.25 |
| B-risk5%      | SUI_USDT_USDT    |        9 | 11.1%      |     -5.65 |     -0.63 |    -19.3  |

## Motifs de rejet des setups (diagnostic)

| motif        |   barres |
|:-------------|---------:|
| trend_filter |   630603 |
| no_new_high  |    26344 |
| ok           |    16221 |
| stop_too_far |     3855 |
| rr_too_low   |     2700 |
| l2_too_far   |     1734 |
| no_l2        |      285 |

## Univers

AAVE_USDT_USDT, AR_USDT_USDT, AVAX_USDT_USDT, BCH_USDT_USDT, BNB_USDT_USDT, BTC_USDT_USDT, DASH_USDT_USDT, ENS_USDT_USDT, ETH_USDT_USDT, FIL_USDT_USDT, GIGGLE_USDT_USDT, HYPE_USDT_USDT, ICP_USDT_USDT, INJ_USDT_USDT, LINK_USDT_USDT, LIT_USDT_USDT, OKB_USDT_USDT, ORDI_USDT_USDT, SOL_USDT_USDT, STRK_USDT_USDT, SUI_USDT_USDT, TAO_USDT_USDT, TRUMP_USDT_USDT, UNI_USDT_USDT, VVV_USDT_USDT, WLD_USDT_USDT, YFI_USDT_USDT, ZEC_USDT_USDT, ZEN_USDT_USDT
