"""
Scraper Banque Mondiale (World Bank) - utilise l'API JSON publique et
documentee de search.worldbank.org (pas de scraping HTML necessaire).

Doc / decouverte empirique des champs :
  https://search.worldbank.org/api/v2/procnotices?format=json&countryshortname_exact=Senegal&rows=2

On interroge l'API une fois par pays UEMOA + Senegal (countryshortname_exact
ne supporte qu'une seule valeur a la fois de maniere fiable).
"""
from __future__ import annotations

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

API_URL = "https://search.worldbank.org/api/v2/procnotices"

# Nom du pays tel qu'attendu par l'API World Bank (countryshortname_exact)
COUNTRIES = {
    "Senegal": "senegal",
    "Mali": "uemoa",
    "Cote d'Ivoire": "uemoa",
    "Benin": "uemoa",
    "Burkina Faso": "uemoa",
    "Niger": "uemoa",
    "Togo": "uemoa",
    "Guinea-Bissau": "uemoa",
}

ROWS_PER_COUNTRY = 15


class WorldBankScraper(BaseScraper):
    source_id = "worldbank"
    source_name = "Banque Mondiale"
    source_url = "https://projects.worldbank.org/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        for country, zone in COUNTRIES.items():
            try:
                items.extend(self._fetch_country(country, zone))
            except Exception:
                # Une source qui echoue pour un pays ne doit pas bloquer les autres
                continue
        return items

    def _fetch_country(self, country: str, zone: str) -> list[TenderItem]:
        params = {
            "format": "json",
            "countryshortname_exact": country,
            "rows": ROWS_PER_COUNTRY,
            "os": 0,
        }
        resp = self.get(API_URL, params=params)
        data = resp.json()
        notices = data.get("procnotices", [])
        # procnotices peut etre une liste OU un dict {id: {...}} selon les versions de l'API
        if isinstance(notices, dict):
            notices = list(notices.values())

        results = []
        for n in notices:
            title = self.clean_text(n.get("bid_description") or n.get("project_name") or "Avis de marche")
            project_id = n.get("project_id", "")
            notice_id = n.get("id", "")
            url = f"https://projects.worldbank.org/en/projects-operations/project-detail/{project_id}" if project_id else "https://projects.worldbank.org/"

            category = "appel_offre"
            method_name = (n.get("procurement_method_name") or "").lower()
            if "expression" in method_name or "interest" in method_name or "eoi" in method_name:
                category = "ami"

            results.append(TenderItem(
                title=title or n.get("project_name") or "Avis de marche - Banque Mondiale",
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity=self.clean_text(n.get("contact_organization")),
                category=category,
                country=country,
                published_date=self._to_iso(n.get("noticedate") or n.get("submission_date")),
                deadline_date=self._to_iso(n.get("submission_deadline_date")),
                description=self.clean_text(n.get("project_name")),
                dedupe_key=f"worldbank|{notice_id or url}",
            ))
        return results

    @staticmethod
    def _to_iso(value):
        if not value:
            return None
        # Formats vus : "06-Jul-2026" ou "2026-07-06T00:00:00Z"
        try:
            if "T" in value:
                return value.split("T")[0]
            from datetime import datetime
            return datetime.strptime(value, "%d-%b-%Y").date().isoformat()
        except Exception:
            return value
