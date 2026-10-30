# Diagnostic IA — Biscuiterie de l'Abbaye (Lonlay-l'Abbaye, Orne)

## 1. Résumé de l'activité

La Biscuiterie de l'Abbaye est une biscuiterie familiale (SA, SIREN 376 450 029) installée à Lonlay-l'Abbaye (Orne, Normandie), dirigée par la famille Lebaudy depuis sa création en 1964 (président actuel : Charles Lebaudy, après 40 ans de direction par son père). L'effectif se situe selon les sources entre ~250 et ~280 salariés (tranche INSEE officielle : 250-499 salariés ; presse économique régionale : 266 à 280 ; à confirmer avec le dirigeant), pour un chiffre d'affaires de l'ordre de 42 à 49 M€ selon l'année (Le Journal des Entreprises, Xerfi). L'entreprise fabrique des sablés et biscuits (gammes bio depuis les années 1980, gammes diététiques/hyperprotéinées, projet de ligne vegan), vendus sous sa propre marque (via boutique/site et GMS) et en marque de distributeur (MDD) — la part respective des deux canaux varie selon les sources (20 % à 80 % de marque propre selon la date de l'article, à vérifier). Elle exporte environ 15 % de son CA, dispose de deux sites de production et a investi 10 M€ dans une 4e ligne de production et un nouvel entrepôt. Elle détient le label Entreprise du Patrimoine Vivant ; aucune source ne mentionne d'appartenance à un groupe (société indépendante, capital familial).

*Sources : Le Journal des Entreprises, Xerfi, INSEE/Sirene (via travail-industrie.com), patrimoine-normand.com, entreprises.gouv.fr, site institutionnel biscuiterie-abbaye.com.*

## 2. Trois cas d'usage IA prioritaires

### 1. Qualité — contrôle visuel automatisé des biscuits en sortie de ligne
- **Problème visé** : détection manuelle ou par capteurs simples des défauts (casse, couleur de cuisson, forme, corps étrangers) sur des lignes à cadence élevée, avec risque de non-conformités en MDD (exigences qualité strictes des distributeurs) et de rebuts non détectés.
- **Gain attendu (estimation sectorielle agroalimentaire, à affiner)** : -15 à -30 % de rebuts/réclamations qualité, réduction du temps de contrôle manuel.
- **Difficulté de mise en œuvre** : moyenne (nécessite caméras/capteurs sur ligne + intégration avec le pilotage de production existant).

### 2. Prévision des ventes — anticipation de la demande MDD et marque propre
- **Problème visé** : plans de production et approvisionnements matières (beurre, farine, sucre) calés sur des prévisions souvent peu fines, avec un mix produit complexe (saisonnalité des biscuits, promos GMS, contrats MDD à volumes variables).
- **Gain attendu (estimation sectorielle, à affiner)** : -10 à -20 % de surstocks/ruptures, meilleure allocation des lignes de production entre marque propre et MDD.
- **Difficulté de mise en œuvre** : moyenne (données de ventes/historique généralement disponibles en ERP, mais nécessite fiabilisation et intégration des contraintes contractuelles MDD).

### 3. Énergie — optimisation de la cuisson et du pilotage des fours
- **Problème visé** : les fours de biscuiterie sont un poste énergétique majeur ; pilotage souvent basé sur des consignes fixes, peu réactif aux variations de pâte/cadence, avec un contexte de hausse des coûts énergétiques.
- **Gain attendu (estimation sectorielle agroalimentaire/industrie IAA, à affiner)** : -5 à -15 % de consommation énergétique sur les lignes de cuisson.
- **Difficulté de mise en œuvre** : élevée (nécessite instrumentation des fours, données de process fiables, et tests prudents pour ne pas affecter la qualité produit).

## 3. Question d'ouverture pour le dirigeant

« Sur vos lignes de production, où perdez-vous aujourd'hui le plus de temps ou de matière entre le contrôle qualité manuel et les ajustements de cadence liés aux commandes MDD — et avez-vous déjà des données (contrôles qualité, historique de commandes) qui pourraient être exploitées, ou tout reste-t-il encore sur papier/Excel ? »
