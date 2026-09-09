#!/usr/bin/env python3
"""
Prospection ciblée de PME agroalimentaires (Sirene + Pappers).

Construit une liste d'établissements agroalimentaires (10.51Z, 10.61*,
10.71C, 10.72Z, 10.89Z, 10.91Z) de 50 à 199 salariés dans les départements
44/35 (option 49/53/56), enrichit chaque société avec le nom du dirigeant
via l'API Pappers, et exporte le tout en CSV.

Variables d'environnement requises :
    SIRENE_API_KEY   Clé d'intégration Sirene/INSEE (portail api.insee.fr,
                      header "X-INSEE-Api-Key-Integration"). Alias accepté :
                      INSEE_API_KEY.
    PAPPERS_API_KEY  Jeton API Pappers (https://api.pappers.fr). Facultatif
                      en mode --dry-run.

Exemples :
    # Test rapide, gratuit, sans toucher au quota Pappers
    python prospecter_pme_agroalimentaire.py --dry-run

    # Run complet, corridor élargi Rennes/Vitré/Fougères
    python prospecter_pme_agroalimentaire.py --elargir-corridor -o prospects.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

LOG = logging.getLogger("prospection_agro")

SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11/siret"
PAPPERS_BASE_URL = "https://api.pappers.fr/v2/entreprise"

# Codes NAF rév. 2 ciblés. "10.61*" couvre 10.61A/B/C (meunerie et travail
# des grains), qui n'ont pas de code générique "10.61Z".
NAF_CODES = [
    "10.51Z",
    "10.61*",
    "10.71C",
    "10.72Z",
    "10.89Z",
    "10.91Z",
]

NAF_LIBELLES = {
    "10.51Z": "Exploitation de laiteries et fabrication de fromage",
    "10.61A": "Meunerie",
    "10.61B": "Autres activités du travail des grains",
    "10.61C": "Production de farines et produits amylacés",
    "10.71A": "Fabrication industrielle de pain et de pâtisserie fraîche",
    "10.71B": "Cuisson de produits de boulangerie",
    "10.71C": "Boulangerie et boulangerie-pâtisserie",
    "10.71D": "Pâtisserie",
    "10.72Z": "Fabrication de biscuits, biscottes et pâtisseries de conservation",
    "10.89Z": "Fabrication d'autres produits alimentaires n.c.a.",
    "10.91Z": "Fabrication d'aliments pour animaux de ferme",
}

# Tranches d'effectif Sirene : 41 = 50 à 99 salariés, 42 = 100 à 199 salariés.
TRANCHE_EFFECTIF_LIBELLES = {
    "41": "50 à 99 salariés",
    "42": "100 à 199 salariés",
}

DEPARTEMENTS_BASE = ["44", "35"]
DEPARTEMENTS_ELARGIS = ["49", "53", "56"]
DEFAULT_TRANCHES = ["41", "42"]

CSV_COLUMNS = [
    "raison_sociale",
    "siren",
    "siret",
    "adresse",
    "code_naf",
    "libelle_naf",
    "departement",
    "tranche_effectif",
    "dirigeant",
    "telephone",
    "site_web",
]

DEFAULT_QUOTA_STATE_PATH = Path(__file__).resolve().parent / ".pappers_quota_state.json"


class PappersQuotaError(Exception):
    """Levée quand l'API Pappers signale un dépassement de quota."""


# --------------------------------------------------------------------------
# Sirene
# --------------------------------------------------------------------------

def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    max_retries: int = 4,
    backoff_base: float = 2.0,
    **kwargs: Any,
) -> requests.Response:
    """Exécute une requête HTTP avec retries + backoff exponentiel sur 429/5xx."""
    last_exc: Exception | None = None
    resp: requests.Response | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = session.request(method, url, timeout=30, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            resp = None

        if resp is not None:
            if resp.status_code == 200:
                return resp
            if resp.status_code not in (429, 500, 502, 503, 504):
                resp.raise_for_status()
            LOG.warning(
                "HTTP %s sur %s (tentative %d/%d)",
                resp.status_code, url, attempt + 1, max_retries + 1,
            )

        if attempt < max_retries:
            time.sleep(backoff_base * (2 ** attempt))

    if resp is not None:
        resp.raise_for_status()
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Échec de la requête vers {url} sans réponse HTTP")


def build_sirene_query(departement: str, tranches: list[str]) -> str:
    naf_clause = "(" + " OR ".join(f"activitePrincipaleEtablissement:{c}" for c in NAF_CODES) + ")"
    tranche_clause = "(" + " OR ".join(f"trancheEffectifsEtablissement:{t}" for t in tranches) + ")"
    clauses = [
        naf_clause,
        f"codePostalEtablissement:{departement}*",
        "etatAdministratifEtablissement:A",
        tranche_clause,
    ]
    return " AND ".join(clauses)


def fetch_sirene_departement(
    session: requests.Session,
    api_key: str,
    departement: str,
    tranches: list[str],
    page_size: int = 1000,
) -> list[dict]:
    """Récupère tous les établissements Sirene pour un département, avec pagination par curseur."""
    query = build_sirene_query(departement, tranches)
    headers = {"X-INSEE-Api-Key-Integration": api_key, "Accept": "application/json"}

    results: list[dict] = []
    curseur = "*"
    total: int | None = None

    while True:
        params = {"q": query, "nombre": page_size, "curseur": curseur}
        resp = request_with_retry(session, "GET", SIRENE_BASE_URL, headers=headers, params=params)
        data = resp.json()
        header = data.get("header", {})
        total = header.get("total", total)
        etablissements = data.get("etablissements", [])
        results.extend(etablissements)

        LOG.info(
            "  Sirene dept %s : %d/%s établissements récupérés",
            departement, len(results), total if total is not None else "?",
        )

        next_curseur = header.get("curseurSuivant")
        if not etablissements or not next_curseur or next_curseur == curseur:
            break
        curseur = next_curseur

    return results


def extract_periode_courante(etab: dict) -> dict:
    periodes = etab.get("periodesEtablissement") or []
    return periodes[0] if periodes else etab


def build_adresse(adresse: dict) -> str:
    voie_parts = [
        adresse.get("numeroVoieEtablissement"),
        adresse.get("typeVoieEtablissement"),
        adresse.get("libelleVoieEtablissement"),
    ]
    voie = " ".join(p for p in voie_parts if p)
    cp = (adresse.get("codePostalEtablissement") or "").strip()
    commune = (adresse.get("libelleCommuneEtablissement") or "").strip()
    ville = f"{cp} {commune}".strip()
    return ", ".join(p for p in [voie, ville] if p)


def parse_etablissement(etab: dict) -> dict:
    periode = extract_periode_courante(etab)
    unite = etab.get("uniteLegale", {}) or {}
    adresse = etab.get("adresseEtablissement", {}) or {}

    denomination = (
        unite.get("denominationUniteLegale")
        or " ".join(filter(None, [unite.get("prenom1UniteLegale"), unite.get("nomUniteLegale")]))
        or "Nom inconnu"
    ).strip()

    code_naf = periode.get("activitePrincipaleEtablissement") or ""
    tranche_code = periode.get("trancheEffectifsEtablissement") or ""
    etat = periode.get("etatAdministratifEtablissement") or ""
    cp = (adresse.get("codePostalEtablissement") or "")

    return {
        "raison_sociale": denomination,
        "siren": etab.get("siren", ""),
        "siret": etab.get("siret", ""),
        "adresse": build_adresse(adresse),
        "code_naf": code_naf,
        "libelle_naf": NAF_LIBELLES.get(code_naf, ""),
        "departement": cp[:2],
        "_tranche_effectif_code": tranche_code,
        "_etat_administratif": etat,
        "dirigeant": "",
        "telephone": "",
        "site_web": "",
    }


def collect_sirene(
    api_key: str,
    departements: list[str],
    tranches: list[str],
    page_size: int = 1000,
) -> list[dict]:
    session = requests.Session()
    parsed: list[dict] = []
    seen_sirets: set[str] = set()

    for dept in departements:
        LOG.info(
            "Interrogation Sirene — département %s (NAF ciblés, tranches %s)...",
            dept, "/".join(tranches),
        )
        raw = fetch_sirene_departement(session, api_key, dept, tranches, page_size=page_size)
        for etab in raw:
            row = parse_etablissement(etab)
            if not row["siret"] or row["siret"] in seen_sirets:
                continue
            seen_sirets.add(row["siret"])
            parsed.append(row)

    LOG.info("Sirene brut : %d établissements récupérés (tous départements confondus)", len(parsed))

    filtered = [
        r for r in parsed
        if r["_etat_administratif"] == "A" and r["_tranche_effectif_code"] in tranches
    ]
    for row in filtered:
        code = row.pop("_tranche_effectif_code")
        row["tranche_effectif"] = TRANCHE_EFFECTIF_LIBELLES.get(code, code)
        row.pop("_etat_administratif", None)

    LOG.info(
        "Après filtre effectif salarié (50-199) + statut actif : %d établissements",
        len(filtered),
    )
    return filtered


# --------------------------------------------------------------------------
# Pappers
# --------------------------------------------------------------------------

PRIORITY_QUALITES = [
    "président", "directeur général", "pdg", "gérant", "co-gérant", "gerant",
]


def pick_dirigeant(representants: list[dict]) -> str:
    if not representants:
        return ""

    def rank(rep: dict) -> int:
        qualite = (rep.get("qualite") or "").lower()
        for i, kw in enumerate(PRIORITY_QUALITES):
            if kw in qualite:
                return i
        return len(PRIORITY_QUALITES)

    best = sorted(representants, key=rank)[0]
    nom = best.get("nom_complet") or " ".join(
        filter(None, [best.get("prenom"), best.get("nom")])
    )
    qualite = best.get("qualite")
    if nom and qualite:
        return f"{nom} ({qualite})"
    return nom or ""


def fetch_pappers_entreprise(session: requests.Session, api_key: str, siren: str) -> dict | None:
    params = {"api_token": api_key, "siren": siren}
    resp = session.get(PAPPERS_BASE_URL, params=params, timeout=30)
    if resp.status_code in (402, 429):
        raise PappersQuotaError(f"Quota Pappers dépassé (HTTP {resp.status_code})")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def apply_pappers_data(row: dict, data: dict) -> None:
    representants = data.get("representants") or []
    dirigeant = pick_dirigeant(representants)
    if dirigeant:
        row["dirigeant"] = dirigeant
    row["telephone"] = data.get("telephone") or row["telephone"]
    row["site_web"] = data.get("site_internet") or data.get("site_web") or row["site_web"]


def load_quota_state(path: Path) -> dict:
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    current_month = date.today().strftime("%Y-%m")
    if data.get("month") != current_month:
        data = {"month": current_month, "count": 0}
    return data


def save_quota_state(path: Path, state: dict) -> None:
    try:
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        LOG.warning("Impossible d'enregistrer l'état du quota Pappers (%s) : %s", path, exc)


def enrich_with_pappers(
    rows: list[dict],
    api_key: str,
    quota: int,
    delay: float,
    state_path: Path,
    max_calls: int | None = None,
) -> None:
    state = load_quota_state(state_path)
    remaining = max(quota - state.get("count", 0), 0)
    if max_calls is not None:
        remaining = min(remaining, max_calls)

    LOG.info(
        "Quota Pappers restant estimé ce mois-ci : %d (quota mensuel configuré : %d)",
        remaining, quota,
    )
    if remaining <= 0:
        LOG.warning("Quota Pappers déjà épuisé pour ce mois — aucun dirigeant ne sera enrichi.")

    session = requests.Session()
    enriched_count = 0
    quota_exhausted = remaining <= 0

    for row in rows:
        if quota_exhausted:
            continue

        try:
            data = fetch_pappers_entreprise(session, api_key, row["siren"])
        except PappersQuotaError as exc:
            LOG.warning("%s — arrêt de l'enrichissement, dirigeants restants laissés vides.", exc)
            quota_exhausted = True
            continue
        except requests.RequestException as exc:
            LOG.warning(
                "Erreur Pappers pour SIREN %s (%s) : %s — dirigeant laissé vide",
                row["siren"], row["raison_sociale"], exc,
            )
            continue
        finally:
            state["count"] = state.get("count", 0) + 1
            remaining -= 1
            save_quota_state(state_path, state)
            time.sleep(delay)

        if data:
            apply_pappers_data(row, data)
            if row["dirigeant"]:
                enriched_count += 1

    LOG.info(
        "Après enrichissement Pappers : %d/%d établissements avec un dirigeant identifié",
        enriched_count, len(rows),
    )


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def write_csv(rows: list[dict], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Construit une liste ciblée de PME agroalimentaires (Sirene + Pappers) "
            "pour de la prospection commerciale."
        )
    )
    parser.add_argument(
        "--departements", default=",".join(DEPARTEMENTS_BASE),
        help=f"Départements séparés par des virgules (défaut : {','.join(DEPARTEMENTS_BASE)})",
    )
    parser.add_argument(
        "--elargir-corridor", action="store_true",
        help=f"Ajoute les départements {','.join(DEPARTEMENTS_ELARGIS)} (corridor Rennes/Vitré/Fougères)",
    )
    parser.add_argument(
        "--tranches", default=",".join(DEFAULT_TRANCHES),
        help="Codes de tranche d'effectif Sirene à cibler (défaut : 41,42 = 50-199 salariés)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="N'interroge que Sirene (gratuit) : le champ dirigeant reste vide, aucun appel Pappers.",
    )
    parser.add_argument(
        "-o", "--output", default="prospects_agroalimentaire.csv",
        help="Chemin du fichier CSV de sortie (défaut : prospects_agroalimentaire.csv)",
    )
    parser.add_argument(
        "--pappers-quota", type=int,
        default=int(os.environ.get("PAPPERS_MONTHLY_QUOTA", "250")),
        help="Quota mensuel Pappers à ne pas dépasser (défaut : 250, plan gratuit)",
    )
    parser.add_argument(
        "--pappers-delay", type=float,
        default=float(os.environ.get("PAPPERS_DELAY_SECONDS", "1.5")),
        help="Délai en secondes entre deux appels Pappers (défaut : 1.5)",
    )
    parser.add_argument(
        "--pappers-max-calls", type=int, default=None,
        help="Plafond optionnel d'appels Pappers pour ce run (au-delà du quota mensuel restant)",
    )
    parser.add_argument(
        "--sirene-page-size", type=int, default=1000,
        help="Taille de page pour la pagination Sirene (défaut : 1000, max autorisé par l'API)",
    )
    parser.add_argument(
        "--quota-state-file", default=str(DEFAULT_QUOTA_STATE_PATH),
        help="Fichier local de suivi du quota Pappers consommé ce mois-ci",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs en mode debug")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    sirene_key = os.environ.get("SIRENE_API_KEY") or os.environ.get("INSEE_API_KEY")
    if not sirene_key:
        LOG.error(
            "Clé API Sirene manquante. Définissez la variable d'environnement SIRENE_API_KEY "
            "(clé d'intégration du portail api.insee.fr)."
        )
        return 1

    departements = [d.strip() for d in args.departements.split(",") if d.strip()]
    if args.elargir_corridor:
        for dept in DEPARTEMENTS_ELARGIS:
            if dept not in departements:
                departements.append(dept)
    tranches = [t.strip() for t in args.tranches.split(",") if t.strip()]

    LOG.info("Départements ciblés : %s", ", ".join(departements))
    LOG.info("Tranches d'effectif ciblées : %s", ", ".join(tranches))
    LOG.info("Mode dry-run : %s", "oui (Pappers désactivé)" if args.dry_run else "non")

    try:
        rows = collect_sirene(sirene_key, departements, tranches, page_size=args.sirene_page_size)
    except requests.HTTPError as exc:
        LOG.error("Échec de l'appel Sirene : %s", exc)
        return 1

    if not rows:
        LOG.warning("Aucun établissement trouvé avec ces critères.")

    if rows and not args.dry_run:
        pappers_key = os.environ.get("PAPPERS_API_KEY")
        if not pappers_key:
            LOG.warning(
                "Clé API Pappers manquante (PAPPERS_API_KEY) — enrichissement ignoré, "
                "dirigeants laissés vides."
            )
        else:
            enrich_with_pappers(
                rows,
                api_key=pappers_key,
                quota=args.pappers_quota,
                delay=args.pappers_delay,
                state_path=Path(args.quota_state_file),
                max_calls=args.pappers_max_calls,
            )
    else:
        LOG.info("Enrichissement Pappers ignoré (dry-run ou aucun établissement trouvé).")

    write_csv(rows, args.output)
    LOG.info("Export terminé : %s (%d lignes)", args.output, len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
