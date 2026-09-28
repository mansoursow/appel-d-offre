"""
Relais local : collecte depuis Dakar les sites injoignables depuis l'hebergeur.

Le portail officiel www.marchespublics.sn n'accepte que les connexions venant
du Senegal. L'application etant hebergee en Europe (Railway), elle ne peut pas
l'interroger. Ce programme, lance depuis un poste a Dakar, fait la collecte
puis depose les avis sur le site via /api/ingest/<source>.

Utilisation (depuis le dossier app/backend) :

    venv/Scripts/python.exe collect_local.py

Reglages, par variable d'environnement ou par fichier :
  APP_URL       adresse du site        (defaut https://app.adoc-consulting.com)
  INGEST_TOKEN  jeton du relais        (sinon lu dans le fichier .ingest_token)

Le jeton doit etre IDENTIQUE a la variable INGEST_TOKEN configuree sur Railway.
En cas d'echec, le programme renvoie un code de sortie different de zero et
ecrit la raison a l'ecran (visible dans le journal du planificateur Windows).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app.config import SOURCE_BY_ID  # noqa: E402
from app.scrapers.marchespublics_sn import MarchesPublicsSNScraper  # noqa: E402

# Sources collectees par le relais : identifiant -> scraper
RELAYED_SCRAPERS = {
    "marchespublics_sn": MarchesPublicsSNScraper(),
}

DEFAULT_APP_URL = "https://app.adoc-consulting.com"
TOKEN_FILE = os.path.join(BASE_DIR, ".ingest_token")


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
    return True


def main() -> int:
    app_url = os.environ.get("APP_URL", DEFAULT_APP_URL)
    token = _token()
    if not token:
        _log("Aucun jeton : renseigner INGEST_TOKEN ou le fichier .ingest_token")
        return 2

    _log(f"Relais local vers {app_url}")
    echecs = 0
    for source_id, scraper in RELAYED_SCRAPERS.items():
        if not collect(source_id, scraper, app_url, token):
            echecs += 1
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
