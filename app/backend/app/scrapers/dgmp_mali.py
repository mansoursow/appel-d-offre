"""
Scraper Mali - DGMP-DSP (Direction Generale des Marches Publics et des
Delegations de Service Public), site officiel www.dgmp.gouv.ml.

Table HTML : Nom Autorite Contractante | Nom service | Libelle du Dossier |
Date du dossier | Dossier (lien de telechargement).
Deux pages : Avis d'appels d'offres (node/71) et Avis de manifestation
d'interet (node/66).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

PAGES = [
    ("https://www.dgmp.gouv.ml/?q=node/71", "appel_offre"),
    ("https://www.dgmp.gouv.ml/?q=node/66", "ami"),
]
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class DgmpMaliScraper(BaseScraper):
    source_id = "dgmp_mali"
    source_name = "Site officiel Mali (DGMP)"
    source_url = "https://www.dgmp.gouv.ml/"
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        items = []
        for url, category in PAGES:
            try:
                resp = self.get(url)
            except Exception:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            items.extend(self._parse(soup, category))
        return items

    def _parse(self, soup: BeautifulSoup, category: str) -> list[TenderItem]:
        results = []
        table = None
        for t in soup.find_all("table"):
            header_text = t.get_text(" ").lower()
            if "libell" in header_text and "dossier" in header_text:
                table = t
                break
        if table is None:
            return results

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            entite = self.clean_text(cells[0].get_text())
            service = self.clean_text(cells[1].get_text())
            libelle = self.clean_text(cells[2].get_text())
            date_text = self.clean_text(cells[3].get_text()) if len(cells) > 3 else None

            if not libelle:
                continue

            link = None
            if len(cells) > 4:
                link = cells[4].find("a")
            if not link:
                link = tr.find("a", href=True)
            href = link.get("href") if link else None
            url = self._absolute(href) if href else self.source_url

            date_match = DATE_RE.search(date_text) if date_text else None
            published = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else None

            results.append(TenderItem(
                title=libelle,
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=entite or service,
                category=category,
                country="Mali",
                published_date=published,
                deadline_date=None,
                description=service if service != entite else None,
                dedupe_key=f"dgmp_mali|{url}|{libelle[:80]}",
            ))
        return results

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.dgmp.gouv.ml" + ("" if href.startswith("/") else "/") + href
