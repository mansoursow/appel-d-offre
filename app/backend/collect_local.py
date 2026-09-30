"""
Relais local : collecte depuis Dakar les sites injoignables depuis l'hebergeur.

Le portail officiel www.marchespublics.sn n'accepte que les connexions venant
du Senegal. L'application etant hebergee en Europe (Railway), elle ne peut pas
l'interroger. Ce programme, lance depuis un poste a Dakar, fait la collecte
puis depose les avis sur le site via /api/ingest/<source>.

Utilisation (depuis le dossier app/backend) :

    venv/Scripts/python.exe collect_local.py

Il collecte aussi les PLANS DE PASSATION (ce que chaque autorite prevoit de
lancer dans l'annee), une fois par semaine : leur parcours dure ~45 min.

Le programme est prevu pour etre lance PLUSIEURS FOIS PAR JOUR (toutes les
heures) : il note dans .ingest_state.json le jour de sa derniere reussite. Si
la collecte du jour est deja faite, il s'arrete aussitot sans rien refaire.
Tant qu'elle n'a pas reussi -- poste eteint, coupure Internet, site qui ne
repond pas -- chaque lancement retente. On a donc au moins une mise a jour par
jour des que la machine est allumee et connectee.

Reglages, par variable d'environnement ou par fichier :
  APP_URL       adresse du site        (defaut https://app.adoc-consulting.com)
  INGEST_TOKEN  jeton du relais        (sinon lu dans le fichier .ingest_token)
  --force       refait la collecte meme si elle a deja reussi aujourd'hui

Le jeton doit etre IDENTIQUE a la variable INGEST_TOKEN configuree sur Railway.
En cas d'echec, le programme renvoie un code de sortie different de zero et
ecrit la raison a l'ecran (visible dans le journal du planificateur Windows).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.config import SOURCE_BY_ID  # noqa: E402
from app.scrapers.marchespublics_sn import MarchesPublicsSNScraper  # noqa: E402
from app.scrapers.plans_sn import ANNEE as PLANS_ANNEE, PlansSenegalScraper  # noqa: E402

# Sources collectees par le relais : identifiant -> scraper
RELAYED_SCRAPERS = {
    "marchespublics_sn": MarchesPublicsSNScraper(),
}

DEFAULT_APP_URL = "https://app.adoc-consulting.com"
# Les plans de passation changent rarement (quelques revisions par an) et leur
# collecte dure environ 45 min : une fois par semaine suffit.
PLANS_TOUS_LES_JOURS = int(os.environ.get("PLANS_INTERVALLE_JOURS", "7"))
PLANS_TAILLE_LOT = 500
TOKEN_FILE = os.path.join(BASE_DIR, ".ingest_token")
# Jour de la derniere collecte reussie, par source.
STATE_FILE = os.path.join(BASE_DIR, ".ingest_state.json")


def _log(message: str) -> None:
    print(f"{datetime.now():%d/%m/%Y %H:%M:%S}  {message}", flush=True)


def _token() -> str:
    token = os.environ.get("INGEST_TOKEN", "").strip()
    if token:
        return token
    if os.path.isfile(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    return ""


def _read_state() -> dict:
    """Jour de la derniere collecte reussie, par source."""
    try:
        with open(STATE_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _mark_success(source_id: str) -> None:
    state = _read_state()
    state[source_id] = date.today().isoformat()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
    except OSError as exc:  # disque plein, dossier en lecture seule...
        _log(f"impossible d'enregistrer l'etat du relais ({exc})")


def _plans_a_refaire(state: dict) -> bool:
    """Les plans sont rafraichis tous les PLANS_INTERVALLE_JOURS jours."""
    dernier = state.get("plans_sn")
    if not dernier:
        return True
    try:
        ecart = (date.today() - date.fromisoformat(dernier)).days
    except ValueError:
        return True
    return ecart >= PLANS_TOUS_LES_JOURS


def collect(source_id: str, scraper, app_url: str, token: str) -> bool:
    name = SOURCE_BY_ID.get(source_id, {}).get("name", source_id)
    try:
        items = scraper.fetch()
    except Exception as exc:
        _log(f"{name} : site injoignable depuis ce poste ({exc})")
        return False

    payload = {"items": [
        {
            "title": item.title,
            "url": item.url,
            "entity": item.entity,
            "category": item.category,
            "country": item.country,
            "zone": item.zone,
            "published_date": item.published_date,
            "deadline_date": item.deadline_date,
            "description": item.description,
            "dedupe_key": item.dedupe_key,
        }
        for item in items
    ]}

    try:
        resp = requests.post(
            f"{app_url.rstrip('/')}/api/ingest/{source_id}",
            json=payload,
            headers={"X-Ingest-Token": token},
            timeout=120,
        )
    except Exception as exc:
        _log(f"{name} : le site ne repond pas ({exc})")
        return False

    if resp.status_code != 200:
        _log(f"{name} : depot refuse ({resp.status_code}) {resp.text[:200]}")
        return False

    data = resp.json()
    _log(f"{name} : {data['total_found']} avis envoyes, {data['new_items']} nouveau(x)")
    _mark_success(source_id)
    return True


def collect_plans(app_url: str, token: str) -> bool:
    """Plans de passation : ce que chaque autorite prevoit de lancer.

    Le parcours interroge une page par autorite (environ 880). Chaque paquet
    est envoye au fur et a mesure : une coupure en cours de route laisse donc
    les autorites deja parcourues en place.
    """
    scraper = PlansSenegalScraper()
    debut = datetime.now(timezone.utc).isoformat()
    lot: list[dict] = []
    total = autorites = 0

    def envoyer(dernier: bool) -> bool:
        corps = {"items": lot, "dernier_lot": dernier, "annee": PLANS_ANNEE}
        if dernier:
            corps["collecte_debut"] = debut
        try:
            resp = requests.post(
                f"{app_url.rstrip('/')}/api/ingest/plans",
                json=corps, headers={"X-Ingest-Token": token}, timeout=300,
            )
        except Exception as exc:
            _log(f"Plans de passation : envoi impossible ({exc})")
            return False
        if resp.status_code != 200:
            _log(f"Plans de passation : depot refuse ({resp.status_code}) {resp.text[:200]}")
            return False
        return True

    try:
        for nom, lignes in scraper.parcourir():
            autorites += 1
            for ligne in lignes:
                lot.append({
                    "reference": ligne.reference, "objet": ligne.objet,
                    "type_marche": ligne.type_marche, "mode_passation": ligne.mode_passation,
                    "date_lancement": ligne.date_lancement, "date_attribution": ligne.date_attribution,
                    "autorite": ligne.autorite, "type_autorite": ligne.type_autorite,
                    "annee": ligne.annee, "url": ligne.url, "dedupe_key": ligne.dedupe_key,
                })
            total += len(lignes)
            if len(lot) >= PLANS_TAILLE_LOT:
                if not envoyer(False):
                    return False
                lot = []
                _log(f"Plans de passation : {autorites} autorites parcourues, {total} lignes envoyees")
    except Exception as exc:
        _log(f"Plans de passation : collecte interrompue ({exc})")
        return False

    if not envoyer(True):
        return False
    _log(f"Plans de passation : {autorites} autorites, {total} lignes (annee {PLANS_ANNEE})")
    _mark_success("plans_sn")
    return True


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    force = "--force" in argv

    app_url = os.environ.get("APP_URL", DEFAULT_APP_URL)
    token = _token()
    if not token:
        _log("Aucun jeton : renseigner INGEST_TOKEN ou le fichier .ingest_token")
        return 2

    state = _read_state()
    aujourd_hui = date.today().isoformat()
    a_faire = {
        sid: scraper for sid, scraper in RELAYED_SCRAPERS.items()
        if force or state.get(sid) != aujourd_hui
    }
    plans_a_faire = force or _plans_a_refaire(state)
    if not a_faire and not plans_a_faire:
        # Cas le plus frequent quand la tache tourne toutes les heures : la
        # collecte du jour est deja passee, on ne redemande rien au site.
        _log("Collecte du jour deja faite, rien a refaire.")
        return 0

    _log(f"Relais local vers {app_url}")
    echecs = 0
    for source_id, scraper in a_faire.items():
        if not collect(source_id, scraper, app_url, token):
            echecs += 1
    if plans_a_faire and not collect_plans(app_url, token):
        echecs += 1
    if echecs:
        _log(f"{echecs} source(s) en echec : nouvelle tentative au prochain lancement.")
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
