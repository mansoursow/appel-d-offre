"""
Scraper BOAD (Banque Ouest Africaine de Developpement).

Page /fr/opportunites/appels-doffre/ : liste de cartes, chacune avec un
titre (lien), un type d'avis (Avis d'appel d'offre / Avis de manifestation
d'interet / Resultats.../ Plan de Passation...), une plage de dates
(DD/MM/YYYY - DD/MM/YYYY, optionnelle) et un lien "Voir plus".
Pagination classique ?page=N.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

LISTING_URL = "https://www.boad.org/fr/opportunites/appels-doffre"
DATE_RANGE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
PAGES_TO_FETCH = 3


class BoadScraper(BaseScraper):
    source_id = "boad"
    source_name = "BOAD"
    source_url = "https://www.boad.org/fr"
    default_zone = "uemoa"

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
        for a in soup.find_all("a", href=True):
            if self.clean_text(a.get_text()) != "Voir plus":
                continue
            href = a["href"]

            block = self.find_ancestor_with(a, lambda el: el.find(["h1", "h2", "h3"]) is not None)
            heading = block.find(["h1", "h2", "h3"])
            title = self.clean_text(heading.get_text()) if heading else None
            if not title:
                continue

            block_text = self.clean_text(block.get_text(" ")) or ""
            date_match = DATE_RANGE_RE.search(block_text)
            published, deadline = (None, None)
            if date_match:
                published = self._to_iso(date_match.group(1))
                deadline = self._to_iso(date_match.group(2))

            category = self.guess_category(block_text)
            country, zone = self.guess_country_zone(title, self.default_zone)

            results.append(TenderItem(
                title=title,
                url=self._absolute(href),
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="BOAD",
                category=category,
                country=country,
                published_date=published,
                deadline_date=deadline,
                description=None,
                dedupe_key=f"boad|{href}",
            ))
        return results

    @staticmethod
    def _to_iso(date_str):
        try:
            d, m, y = date_str.split("/")
            return f"{y}-{m}-{d}"
        except Exception:
            return date_str

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.boad.org" + ("" if href.startswith("/") else "/") + href
