"""
Scraper TED (ted.europa.eu) - journal des marches publics de l'UE.

Utilise l'API officielle v3 (POST api.ted.europa.eu/v3/notices/search,
sans cle API) avec un filtre sur les lieux d'execution d'Afrique de
l'Ouest ; les avis europeens "classiques" sont hors perimetre de l'app.
"""
from __future__ import annotations

import requests

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

API_URL = "https://api.ted.europa.eu/v3/notices/search"

# Pays d'Afrique de l'Ouest suivis par l'application (codes ISO alpha-3)
PLACE_CODES = "SEN CIV MLI BEN GIN NER TGO BFA GNB GMB MRT"

ISO3_COUNTRY = {
    "SEN": "Senegal", "CIV": "Cote d'Ivoire", "MLI": "Mali", "BEN": "Benin",
    "GIN": "Guinee", "NER": "Niger", "TGO": "Togo", "BFA": "Burkina Faso",
    "GNB": "Guinee-Bissau", "GMB": "Gambie", "MRT": "Mauritanie",
}


class TedScraper(BaseScraper):
    source_id = "ted_ue"
    source_name = "Union Europeenne (TED)"
    source_url = "https://ted.europa.eu/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        payload = {
            "query": f"place-of-performance IN ({PLACE_CODES}) "
                     f"SORT BY publication-date DESC",
            "fields": [
                "publication-number", "notice-title", "buyer-name",
                "publication-date", "deadline-receipt-tender-date-lot",
                "place-of-performance",
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
            if not pub_number:
                continue
            title = self._multilang(n.get("notice-title")) or f"Avis TED {pub_number}"
            buyer = self._multilang(n.get("buyer-name"))

            deadline = None
            dl = n.get("deadline-receipt-tender-date-lot")
            if isinstance(dl, list) and dl:
                deadline = str(dl[0])[:10]
            elif isinstance(dl, str):
                deadline = dl[:10]

            places = n.get("place-of-performance") or []
            if isinstance(places, str):
                places = [places]
            country = None
            zone = self.default_zone
            for code in places:
                if code in ISO3_COUNTRY:
                    country = ISO3_COUNTRY[code]
                    zone = "senegal" if code == "SEN" else "uemoa"
                    break

            items.append(TenderItem(
                title=title[:300],
                url=f"https://ted.europa.eu/fr/notice/{pub_number}",
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity=buyer,
                category=self.guess_category(title) if self.guess_category(title) != "autre" else "appel_offre",
                country=country,
                published_date=(n.get("publication-date") or "")[:10] or None,
                deadline_date=deadline,
                dedupe_key=f"ted|{pub_number}",
            ))
        return items

    @staticmethod
    def _multilang(value) -> str | None:
        """notice-title / buyer-name : dict {lang: [textes]} ou {lang: texte}."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for lang in ("fra", "eng", *value.keys()):
                v = value.get(lang)
                if isinstance(v, list) and v:
                    return str(v[0])
                if isinstance(v, str) and v:
                    return v
        return None
