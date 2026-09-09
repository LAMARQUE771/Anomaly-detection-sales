# Prospection PME agroalimentaires

Script de constitution d'une liste ciblée de PME agroalimentaires (44/35,
50-199 salariés) pour de la prospection commerciale conseil/formation IA,
avec identification du dirigeant via Pappers.

## Critères de ciblage

- **Codes NAF (rév. 2)** : 10.51Z (industrie laitière), 10.61A/B/C (travail
  des grains / meunerie), 10.71C (boulangerie-pâtisserie industrielle),
  10.72Z (biscuiterie industrielle), 10.89Z (autres produits alimentaires),
  10.91Z (aliments pour animaux de ferme).
- **Départements** : 44, 35 par défaut. `--elargir-corridor` ajoute 49, 53, 56.
- **Effectif** : 50 à 199 salariés (tranches Sirene 41 et 42).
- **Statut** : établissements actifs uniquement (cessations exclues).

## Installation

```bash
cd prospection_agroalimentaire
pip install -r requirements.txt
cp .env.example .env   # puis renseigner SIRENE_API_KEY et PAPPERS_API_KEY
```

## Utilisation

```bash
# Test rapide et gratuit : Sirene uniquement, aucun appel Pappers
python prospecter_pme_agroalimentaire.py --dry-run

# Run complet (44, 35), avec enrichissement dirigeant via Pappers
python prospecter_pme_agroalimentaire.py -o prospects.csv

# Corridor élargi Rennes/Vitré/Fougères (44,35,49,53,56)
python prospecter_pme_agroalimentaire.py --elargir-corridor -o prospects.csv
```

Les clés API peuvent être passées via `.env` (chargé automatiquement si
`python-dotenv` est installé) ou directement comme variables d'environnement
`SIRENE_API_KEY` / `PAPPERS_API_KEY`.

## Sortie

CSV avec les colonnes : `raison_sociale, siren, siret, adresse, code_naf,
libelle_naf, departement, tranche_effectif, dirigeant, telephone, site_web`.

## Gestion du quota Pappers

Le plan gratuit Pappers est limité à 250 requêtes/mois. Le script conserve
un compteur mensuel local (`.pappers_quota_state.json`, non versionné) et
s'arrête d'enrichir dès que le quota est atteint, en laissant les champs
`dirigeant` / `telephone` / `site_web` vides plutôt que de planter. Options
utiles :

- `--pappers-quota` : quota mensuel configuré (défaut 250)
- `--pappers-delay` : délai entre deux appels Pappers, en secondes (défaut 1.5)
- `--pappers-max-calls` : plafond d'appels pour ce run précis

## Logs

Le script journalise le nombre d'établissements à chaque étape : Sirene brut
→ après filtre effectif/statut → après enrichissement Pappers.
