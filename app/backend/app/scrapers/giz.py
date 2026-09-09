"""
Scraper GIZ - cooperation allemande.

Le portail ausschreibungen.giz.de (cosinex) exige JavaScript et une
session : il n'est pas scrapable en HTTP simple. En revanche la GIZ
publie ses appels d'offres europeens sur TED : on interroge donc l'API
officielle TED v3 filtree sur la GIZ comme acheteur.
"""
from __future__ import annotations

import requests

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem
from .ted import TedScraper

API_URL = "https://api.ted.europa.eu/v3/notices/search"


class GizScraper(BaseScraper):
    source_id = "giz"
    source_name = "GIZ"
    source_url = "https://ausschreibungen.giz.de/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        payload = {
            "query": 'buyer-name ~ ("Gesellschaft für Internationale Zusammenarbeit") '
                     "SORT BY publication-date DESC",
            "fields": [
                "publication-number", "notice-title", "buyer-name",
                "publication-date", "deadline-receipt-tender-date-lot",
                "place-of-performance",
            ],
            "limit": 30,
        }
        resp = requests.post(API_URL, json=payload,
                             headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
                             timeout=REQUEST_TIMEOUT + 20)
        resp.raise_for_status()
        notices = resp.json().get("notices", [])

        items: list[TenderItem] = []
        for n in notices:
            pub_number = n.get("publication-number")
            if not pub_number:
                continue
            title = TedScraper._multilang(n.get("notice-title")) or f"Avis GIZ {pub_number}"

            deadline = None
            dl = n.get("deadline-receipt-tender-date-lot")
            if isinstance(dl, list) and dl:
                deadline = str(dl[0])[:10]
            elif isinstance(dl, str):
                deadline = dl[:10]

            country, zone = self.guess_country_zone(title, self.default_zone)

            items.append(TenderItem(
                title=title[:300],
                url=f"https://ted.europa.eu/fr/notice/{pub_number}",
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="GIZ",
                category=self.guess_category(title) if self.guess_category(title) != "autre" else "appel_offre",
                country=country,
                published_date=(n.get("publication-date") or "")[:10] or None,
                deadline_date=deadline,
                dedupe_key=f"giz|{pub_number}",
            ))
        return items
