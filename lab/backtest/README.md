# Moteur de backtest

Le moteur de backtest orchestre l'exécution simulée de stratégies sur des données historiques.

## Architecture

### `engine.py`
- `BacktestEngine`: classe principale qui reçoit une stratégie et des données
- `BacktestResult`: résultats agrégés (trades, PnL, statistiques)
- `Trade`: un trade complètement exécuté (entrée + sortie)
- `BacktestContext`: état du backtest à chaque pas de temps

## Flux d'exécution

1. **Initialisation**
   - Convertir le capital initial CAD → USD (une seule fois)
   - Créer le portefeuille et l'état de risque

2. **Boucle temporelle**
   - Pour chaque date dans les données:
     - Libérer les produits de vente réglés (T+1 ou T+2)
     - Pour chaque symbole de l'univers:
       - Vérifier éligibilité (`universe_filter`)
       - Construire l'historique jusqu'à cette date
       - Appeler `on_bar_close` pour obtenir un signal
       - Exécuter le signal (entrée au marché)

3. **Exécution du signal**
   - Dimensionner la position (risk.py)
   - Vérifier les limites de risque
   - Exécuter l'entrée au prix du marché ou limite
   - Appliquer le glissement (broker_sim.py)
   - Débiter le cash du portefeuille

4. **Gestion de la position**
   - À chaque barre: vérifier l'atteinte du stop/cible
   - Sortie au stop en priorité, glissement appliqué
   - Enregistrer la clôture (PnL, risque utilisé)

5. **Résultats**
   - Agréger les trades (PnL, win rate, drawdown)
   - Calculer l'équité finale en CAD
   - Clôturer le portefeuille (vendre tout si besoin)

## Intégration avec les modules

- **costs.py**: calculs de commissions IBKR (Fixed/Tiered)
- **risk.py**: dimensionnement et limites de risque
- **portfolio.py**: suivi du cash réglé/non réglé
- **broker_sim.py**: exécution simulée avec glissement
- **strategies/base.py**: interface standard pour toutes les stratégies
- **validation/**: walk-forward, bootstrap, tournoi

## Notes

- Phase D initial: le moteur est un squelette
- La gestion complète des positions (suivi, sortie, drawdown) sera implémentée en Phase D
- Les stratégies ne voient pas les dates futures grâce à la construction de l'historique progressif
