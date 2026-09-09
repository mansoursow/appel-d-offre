"""
Scraper ARCOP Cote d'Ivoire (Autorite de Regulation de la Commande Publique).

Les pages de documentation utilisent le plugin WordPress "wp-file-download"
qui affiche une table : Fichier (titre + lien PDF) | Vues | Date publication |
Telecharger. On scrape 2 pages : avis d'appel d'offres + avis a manifestation
d'interet.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

PAGES = [
    ("https://arcop.ci/documentation/avis/avis-dappel-doffres/", "appel_offre"),
    ("https://arcop.ci/documentation/avis/avis-a-manifestation-dinteret/", "ami"),
]
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class ArcopCIScraper(BaseScraper):
    source_id = "arcop_ci"
    source_name = "ARCOP Cote d'Ivoire"
    source_url = "https://arcop.ci/"
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
            if "fichier" in header_text and ("date" in header_text or "vues" in header_text):
                table = t
                break
        if table is None:
            return results

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[0].find("a")
            if not link or not link.get("href"):
                continue
            title = self.clean_text(link.get_text())
            href = link.get("href")
            if not title:
                continue

            date_text = self.clean_text(cells[2].get_text()) if len(cells) > 2 else None
            date_match = DATE_RE.search(date_text) if date_text else None
            published = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else None

            results.append(TenderItem(
                title=title,
                url=href,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity="ARCOP",
                category=category,
                country="Cote d'Ivoire",
                published_date=published,
                deadline_date=None,
                description=None,
                dedupe_key=f"arcop_ci|{href}",
            ))
        return results
