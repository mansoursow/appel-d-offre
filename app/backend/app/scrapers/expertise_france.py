"""
Scraper Expertise France - agence francaise de cooperation technique.

Expertise France passe ses marches sur PLACE (marches-publics.gouv.fr), mais
la liste publique de PLACE melange tous les acheteurs de l'Etat (hopitaux,
armees...) et son filtre par organisme exige un formulaire PRADO avec
session : l'ancien scraper remontait donc les 10 dernieres consultations de
TOUT PLACE, sans aucun avis d'Expertise France.

Comme la GIZ, Expertise France publie ses avis de marche sur TED : on
interroge l'API officielle TED v3 filtree sur Expertise France comme acheteur.
"""
from __future__ import annotations

import requests

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem
from .ted import TedScraper

API_URL = "https://api.ted.europa.eu/v3/notices/search"


class ExpertiseFranceScraper(BaseScraper):
    source_id = "expertise_france"
    source_name = "Expertise France"
    source_url = "https://www.expertisefrance.fr/fr/marches-publics-appels-doffres-expertise-france"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        payload = {
            "query": 'buyer-name ~ ("Expertise France") SORT BY publication-date DESC',
            "fields": [
                "publication-number", "notice-title", "notice-type",
                "publication-date", "deadline-receipt-tender-date-lot",
            ],
            "limit": 40,
        }
        resp = requests.post(API_URL, json=payload,
                             headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
                             timeout=REQUEST_TIMEOUT + 20)
        resp.raise_for_status()
        notices = resp.json().get("notices", [])

        items: list[TenderItem] = []
        for n in notices:
            pub_number = n.get("publication-number")
            # Avis d'attribution (can-*) : le marche est deja passe.
            if not pub_number or str(n.get("notice-type") or "").startswith("can"):
                continue
            title = TedScraper._multilang(n.get("notice-title")) or f"Avis Expertise France {pub_number}"

            deadline = None
            dl = n.get("deadline-receipt-tender-date-lot")
            if isinstance(dl, list) and dl:
                deadline = str(dl[0])[:10]
            elif isinstance(dl, str):
                deadline = dl[:10]

            country, zone = self.guess_country_zone(title, self.default_zone)
            category = self.guess_category(title)

            items.append(TenderItem(
                title=title[:300],
                url=f"https://ted.europa.eu/fr/notice/{pub_number}",
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="Expertise France",
                category=category if category != "autre" else "appel_offre",
                country=country,
                published_date=(n.get("publication-date") or "")[:10] or None,
                deadline_date=deadline,
                dedupe_key=f"expertise_france|{pub_number}",
            ))
        return items
