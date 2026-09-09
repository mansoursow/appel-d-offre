"""
Scraper Banque Islamique de Developpement (IsDB) - project-procurement.

Page /project-procurement/fr/appels-doffres : liste de cartes (titre, statut
Fermer/Closed, type d'avis, pays, date). Paginee (?page=N). On ne garde que
les avis concernant le Senegal ou un pays de l'UEMOA.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..config import SOUS_REGION_COUNTRIES
from .base import BaseScraper, TenderItem

LISTING_URL = "https://www.isdb.org/project-procurement/fr/appels-doffres"
DATE_RE = re.compile(r"\b(\d{1,2}\s+[A-Za-zéûî]+\s+\d{4})\b")
PAGES_TO_FETCH = 4

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06",
    "july": "07", "august": "08", "september": "09", "october": "10", "november": "11", "december": "12",
    "janvier": "01", "février": "02", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
    "juillet": "07", "août": "08", "aout": "08", "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12", "decembre": "12",
}

# Normalisation des variantes de noms de pays vues sur isdb.org
COUNTRY_ALIASES = {
    "cote d'ivoire": "Cote d'Ivoire",
    "cote d ivoire": "Cote d'Ivoire",
    "senegal": "Senegal",
    "mali": "Mali",
    "benin": "Benin",
    "burkina faso": "Burkina Faso",
    "niger": "Niger",
    "togo": "Togo",
    "guinea": "Guinea",
    "guinea-bissau": "Guinea-Bissau",
}


class IsdbScraper(BaseScraper):
    source_id = "isdb"
    source_name = "Banque Islamique de Developpement"
    source_url = LISTING_URL
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        items = []
        seen = set()
        for page in range(PAGES_TO_FETCH):
            url = LISTING_URL if page == 0 else f"{LISTING_URL}?page={page}"
            try:
                resp = self.get(url)
            except Exception:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            page_items = self._parse(soup)
            if not page_items:
                break
            new_count = 0
            for it in page_items:
                if it.url in seen:
                    continue
                seen.add(it.url)
                items.append(it)
                new_count += 1
            if new_count == 0:
                break
        return items

    def _parse(self, soup: BeautifulSoup) -> list[TenderItem]:
        results = []
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=True)
            if not a:
                continue
            title = self.clean_text(a.get_text())
            href = a["href"]
            if not title:
                continue

            block = self.find_ancestor_with(h2, lambda el: DATE_RE.search(el.get_text(" ") or ""))
            block_text = self.clean_text(block.get_text(" ")) or ""

            country = None
            low = block_text.lower()
            for alias, canon in COUNTRY_ALIASES.items():
                if alias in low:
                    country = canon
                    break

            if not country:
                continue  # hors zone d'interet (Senegal + UEMOA uniquement)

            zone = "senegal" if country == "Senegal" else "uemoa"

            results.append(TenderItem(
                title=title,
                url=self._absolute(href),
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="Banque Islamique de Developpement",
                category=self.guess_category(title),
                country=country,
                published_date=None,
                deadline_date=None,
                description=None,
                dedupe_key=f"isdb|{href}",
            ))
        return results

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.isdb.org" + ("" if href.startswith("/") else "/") + href
