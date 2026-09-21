# Brief Claude Code — Laboratoire multi-stratégies (paper-first)

> Place ce fichier à la racine du projet sous le nom `CLAUDE.md` (ou colle-le comme premier message).
> Décompresse `orb_backtest.zip` dans le même dossier : c'est le point de départ du code.

---

## 0. Mission

Construire un **laboratoire de stratégies** qui met plusieurs stratégies en compétition, sur les mêmes données et avec les mêmes frais réels, les mêmes règles de risque et les mêmes critères statistiques. Seules les stratégies qui prouvent un avantage **avec 95 % de confiance après frais** passent à l'étape des alertes Telegram et du compte papier IBKR.

Le but n'est pas de garantir des trades gagnants, c'est impossible. Le but est de ne jamais trader une stratégie dont l'avantage n'est pas démontré.

## 1. Contraintes non négociables

- **Papier seulement.** Aucun identifiant de compte réel n'est demandé ni stocké. Le mode réel est désactivé par défaut et ne s'active qu'avec une décision explicite de Philippe, hors de ce brief.
- Capital de départ de **200 $ CAD**, dans un compte comptant non enregistré (pas de CELI : risque que l'ARC y voie une activité d'entreprise). Pas de marge, pas de vente à découvert, pas d'options, pas de FNB à effet de levier, pas de crypto.
- Courtier cible : **Interactive Brokers Canada**, en compte papier.
- Philippe travaille le jour en succursale et **ne peut pas approuver d'alertes pendant les heures de bureau**. Les stratégies swing sont approuvées le soir. L'ORB intraday garde sa fenêtre de 2 minutes, mais il est pénalisé en conséquence (voir section 6).
- Risque par trade de 2 à 4 $ CAD, avec un plafond absolu de 5 $ **frais aller-retour inclus**. Une seule position ouverte au départ. Pause après 2 pertes consécutives. On ne fait jamais de moyenne à la baisse.
- **Aucune donnée inventée.** Si une donnée manque ou semble suspecte, on s'arrête et on le signale.
- **Honnêteté des résultats.** Un NO-GO est un résultat valide et utile. Ne jamais ajuster les paramètres sur les données hors échantillon pour faire passer une stratégie.

## 2. Méthode de travail

1. Travailler **phase par phase** (section 5) et s'arrêter à la fin de chacune pour la revue de Philippe, avec un résumé court de ce qui est fait, de ce qui a échoué et de la décision requise.
2. Initialiser un dépôt git et faire un commit par étape logique.
3. Utiliser un environnement virtuel Python 3.11+ et un fichier `requirements.txt`.
4. Écrire des tests `pytest` pour les frais, le dimensionnement, le règlement T+1, l'absence de données futures et les sorties stop/cible.
5. Mettre les secrets dans `.env`, ajouté à `.gitignore`. Ne jamais les journaliser.
6. Rédiger les rapports en français.

## 3. Code existant (orb_backtest.zip)

- `orb/config.py` : paramètres (risque, session, coûts IBKR Fixed, règlement).
- `orb/data.py` : chargement de CSV et données synthétiques.
- `orb/indicators.py` : VWAP, volume à la même heure, MA quotidiennes décalées d'un jour, régime du benchmark.
- `orb/backtest.py` : moteur intraday, une position à la fois, cash réglé T+1, journal des rejets.
- `orb/metrics.py` et `run.py` : métriques, sensibilité, rapport go/no-go.

**Constat du test synthétique :** avec 1 à 3 actions par trade, la commission minimale IBKR Fixed (environ 2,74 $ CAD aller-retour) dépasse souvent un gain de 2R. Le modèle de frais est donc le premier point à rendre exact.

## 4. Architecture cible

```
lab/
  data/        fournisseurs (ibkr, alpaca, csv), cache parquet, contrôles qualité
  core/
    costs.py       IBKR Fixed ET Tiered, actions fractionnées, conversion de devises unique
    risk.py        dimensionnement, limites quotidiennes, pause, plafond 5 $
    broker_sim.py  exécution simulée (quotidien + intraday), T+1, écarts, glissement
    portfolio.py   cash réglé/non réglé, équité en CAD
  strategies/
    base.py        interface Strategy
    swing_pullback.py
    rsi2_reversion.py
    momentum_monthly.py
    orb_intraday.py   (port du code existant)
  validation/
    walk_forward.py
    bootstrap.py      IC 95 % de l'espérance
    monte_carlo.py    probabilité de ruine / de drawdown
    tournament.py     classement + verdict
  alerts/       (phase 5 seulement) scanner, Telegram, adaptateur IBKR papier
  reports/
```

**Interface Strategy** (à respecter par chaque plug-in) :

- `timeframe` : `"1d"` ou `"5m"`.
- `universe_filter(symbol, data)` : indique si le symbole est éligible.
- `on_bar_close(ctx) -> Signal | None` : retourne le symbole, le type d'ordre d'entrée (marché à l'ouverture suivante ou limite), le prix limite, le stop, la règle de sortie (cible en R, stop suiveur, sortie temporelle en N barres, ou signal de sortie), l'expiration et un texte d'explication pour Telegram.
- `params_grid()` : la grille de sensibilité, limitée à environ 20 combinaisons pour réduire le surajustement.

Le moteur, et non la stratégie, applique les frais, le risque, le règlement et les limites. Une stratégie ne peut pas contourner ces règles.

## 5. Phases

### Phase A — Données (s'arrêter pour revue)

- **Source principale :** l'API IBKR via `ib_insync`, connectée à TWS ou IB Gateway en mode papier. Barres quotidiennes sur 10 ans ou plus, et barres de 5 minutes sur au moins 3 ans pour l'ORB. Respecter les limites de requêtes historiques d'IBKR (pacing).
- **Sources de secours :** Alpaca (données IEX, clé gratuite) ou Polygon. Pour le quotidien seulement, yfinance est acceptable en recherche. Toujours consigner la source utilisée.
- Utiliser des prix ajustés (dividendes et fractionnements) pour le quotidien.
- Contrôles qualité : jours manquants, barres incohérentes, volumes nuls, sauts suspects. Produire un rapport de qualité par symbole.
- **Univers candidat à tester** (la sélection finale revient au code, selon la liquidité, l'écart et le prix vs 200 $) : SPY, QQQ, IWM, DIA, XLF, XLE, XLK, XLV, XLI, GLD, TLT, EFA, ainsi que XIU.TO, ZSP.TO et XEG.TO. Ajouter un FNB de bons du Trésor court terme (ex. BIL ou SGOV) comme actif « cash » pour le momentum.
- Remplir `events.csv` avec les dates FOMC, IPC et emploi à partir de sources officielles (Fed, BLS), en heure de New York. Ne pas les deviner.

### Phase B — Moteur commun (s'arrêter pour revue)

- Refactoriser selon la section 4. Porter l'ORB existant sans changer sa logique, puis vérifier qu'on retrouve les mêmes résultats.
- **Modèle de frais** avec deux profils :
  - IBKR Fixed : 0,005 $ US par action, minimum 1 $, maximum 1 % de la valeur. Pour le Canada : 0,01 $ CAD par action, minimum 1 $, maximum 0,5 %.
  - IBKR Tiered : 0,0035 $ US par action, minimum environ 0,35 $, plus les frais de bourse et de compensation.
  - **Vérifier les grilles actuelles sur le site d'IBKR et les consigner avec la date.** Ne pas se fier aux chiffres de ce brief.
- **Actions fractionnées** en option, pour pouvoir trader des FNB chers avec 200 $. Vérifier la disponibilité chez IBKR Canada et via l'API, et consigner le résultat. Si elles ne sont pas disponibles, désactiver l'option.
- Conversion CAD vers USD une seule fois au départ, en tenant compte du minimum IBKR. Toute l'équité est présentée en CAD.
- Exécution simulée :
  - Pour les stratégies quotidiennes : signal à la clôture, entrée à l'ouverture suivante avec glissement.
  - Si le stop et la cible sont touchés dans la même barre, on suppose que le stop a été touché en premier.
  - En cas de gap sous le stop, la sortie se fait à l'ouverture.

### Phase C — Les 4 stratégies (s'arrêter pour revue)

Pour chaque stratégie : règles exactes, sans données futures, avec une petite grille de paramètres.

1. **Swing pullback (quotidien).**
   - Conditions : tendance (clôture au-dessus de la SMA 50 et SMA 50 au-dessus de la SMA 200) et benchmark au-dessus de sa SMA 200.
   - Entrée : repli vers l'EMA 20, puis reprise (clôture au-dessus du plus haut de la veille), avec entrée à l'ouverture suivante.
   - Stop : sous le creux du repli moins une fraction d'ATR.
   - Sortie : cible de 2R, ou stop suiveur ATR, ou sortie temporelle après 10 jours.
2. **Retour à la moyenne RSI(2) (quotidien).**
   - Conditions : clôture au-dessus de la SMA 200 et RSI(2) sous 10 (le seuil fait partie de la grille).
   - Entrée à l'ouverture suivante.
   - Sortie : clôture au-dessus de la SMA 5, ou après 5 jours.
   - Stop catastrophe à 2,5 ATR, obligatoire à cause du plafond de 5 $.
   - Tester spécifiquement si l'avantage persiste sur les 5 dernières années par rapport aux années précédentes.
3. **Momentum mensuel (rotation).**
   - Chaque fin de mois, choisir le FNB qui a le meilleur rendement sur 6 ou 12 mois parmi un petit panier. S'il fait moins bien que l'actif « cash », détenir l'actif « cash ».
   - Une position à la fois. Les frais sont minimes.
   - Le stop de 5 $ ne s'applique pas tel quel : documenter le risque autrement (drawdown maximal historique en $).
4. **ORB intraday (existant).**
   - Même logique qu'avant, avec les profils de frais Tiered et fractionné en plus.
   - Pénalité de disponibilité : exclure les signaux pendant les heures où Philippe ne peut pas approuver. Rendre ces heures configurables ; par défaut, aucune approbation entre 9 h 30 et 16 h 00 en semaine, ce qui l'élimine probablement. C'est voulu : on veut savoir si l'ORB reste viable avec les disponibilités réelles.

### Phase D — Validation et tournoi (s'arrêter pour revue ; c'est la décision clé)

- **Walk-forward :** optimiser sur une fenêtre, tester sur la suivante, avancer, puis agréger uniquement les résultats hors échantillon.
- **Bootstrap :** 10 000 rééchantillonnages des trades hors échantillon pour obtenir l'IC 95 % de l'espérance en $ CAD et en R.
- **Monte Carlo :** 10 000 permutations de l'ordre des trades pour estimer la probabilité d'un drawdown de 25 % et de 50 %, la probabilité d'être positif après 50, 100 et 200 trades, et la distribution de l'équité finale.
- **Correction pour tests multiples :** consigner le nombre total de combinaisons testées et exiger que le résultat retenu tienne sur ses voisins de paramètres (pas un pic isolé).
- Ventiler les résultats par régime (tendance et volatilité du benchmark).
- **Critères de passage** (tous obligatoires) :
  - Au moins 200 trades au total pour les stratégies actives (le momentum a un seuil adapté : au moins 10 ans d'historique).
  - Au moins 50 trades hors échantillon.
  - **Borne basse de l'IC 95 % de l'espérance > 0 après frais.**
  - Profit factor hors échantillon supérieur à 1,2.
  - Au moins 60 % des combinaisons voisines positives hors échantillon.
  - Probabilité Monte Carlo d'un drawdown de 50 % inférieure à 5 %.
  - Au moins 3 régimes de marché représentés.
  - Faisable avec 200 $ (quantité supérieure ou égale à 1, ou fractionnée si disponible) et compatible avec les disponibilités de Philippe.
- **Rapport du tournoi :** un tableau de classement, le verdict par stratégie avec la raison exacte de chaque échec, et une recommandation claire.
- **Si aucune stratégie ne passe avec 200 $,** le rapport doit calculer le capital minimal à partir duquel chaque stratégie passerait les critères (tester avec 200, 500, 1 000, 2 500 et 5 000 $). C'est une information décisionnelle, pas un échec.

### Phase E — Alertes et compte papier (seulement pour les stratégies qui ont passé)

- **Scanner du soir** vers 16 h 30 heure de New York (ce qui correspond aussi à l'heure de Montréal) : il calcule les signaux sur les données du jour.
- **Message Telegram**, avec des boutons en ligne Approuver et Refuser. Il contient :
  - le symbole, la stratégie, l'entrée, le stop, la cible ou la règle de sortie, la quantité et le risque en $ CAD frais inclus ;
  - l'état de la tendance et du régime, les événements à venir, et l'IC 95 % historique de la stratégie ;
  - l'expiration : l'approbation est valide jusqu'à 9 h 00 le lendemain.
- **Après approbation :** ordre envoyé **au compte papier IBKR seulement**, accompagné d'un ordre stop protecteur (bracket), avec annulation si le prix d'ouverture sort de la bande permise.
- **Robustesse :**
  - validation des webhooks et callbacks, idempotence (un signal ne peut produire qu'un seul ordre) ;
  - journal d'audit complet ;
  - détection de données périmées et de déconnexions ;
  - commande Telegram `/stop` qui sert de kill switch (annule tout et bloque les nouveaux ordres).
- **Journal papier :** heure du signal, heure de l'alerte, heure de l'approbation, entrée demandée, exécution réelle, glissement, sortie, et comparaison avec le backtest.

### Phase F — Essai papier

- Au moins 4 semaines pour le swing (une semaine ne suffit pas à des trades de plusieurs jours), et assez de trades pour comparer les exécutions au backtest.
- **Critère d'arrêt :** si le glissement réel ou l'espérance papier s'écarte nettement du backtest, on revient à la phase D.
- Le passage au réel ne fait pas partie de ce brief.

## 6. Ce qu'il ne faut pas faire

- Promettre ou afficher un rendement cible. L'objectif de 200 $ vers 5 000 $ n'est pas un critère de succès.
- Ajouter des stratégies ou des indicateurs en cours de route sans les faire passer par le tournoi complet.
- Optimiser sur les données hors échantillon, ou les regarder avant la phase D.
- Construire la phase E avant qu'une stratégie ait réussi la phase D.

## 7. Premier message attendu de Claude Code

Un plan de la phase A (sources, symboles, périodes, format du cache) et la liste des informations à obtenir de Philippe (identifiants papier IBKR via TWS ou Gateway, jeton du bot Telegram plus tard). Ensuite, commencer.
