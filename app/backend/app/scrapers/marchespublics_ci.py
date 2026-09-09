"""
Scraper Cote d'Ivoire - DGMP (Direction Generale des Marches Publics).

La page /appel_offre affiche une table HTML classique :
Numero AO | Type de marche | Objet | Autorite Contractante |
Date de publication | Date limite
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

LISTING_URL = "https://marchespublics.ci/appel_offre"
DATE_RE = re.compile(r"(\d{2})-(\d{2})-(\d{4})")


class MarchesPublicsCIScraper(BaseScraper):
    source_id = "marchespublics_ci"
    source_name = "Cote d'Ivoire Marche public (officiel)"
    source_url = LISTING_URL
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        resp = self.get(LISTING_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = None
        for t in soup.find_all("table"):
            header_text = t.get_text(" ").lower()
            if "num" in header_text and "objet" in header_text:
                table = t
                break
        if table is None:
            return []

        rows = table.find_all("tr")
        items = []
        for tr in rows:
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            numero = self.clean_text(cells[0].get_text())
            type_marche = self.clean_text(cells[1].get_text())
            objet = self.clean_text(cells[2].get_text())
            entite = self.clean_text(cells[3].get_text())
            date_pub = self.clean_text(cells[4].get_text())
            date_limite = self.clean_text(cells[5].get_text())

            if not objet or objet.lower() in ("objet",):
                continue

            link = tr.find("a")
            url = self._absolute(link.get("href")) if link and link.get("href") else LISTING_URL

            items.append(TenderItem(
                title=objet,
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=entite or None,
                category=self.guess_category(f"{type_marche} {objet}"),
                country="Cote d'Ivoire",
                published_date=self._to_iso(date_pub),
                deadline_date=self._to_iso(date_limite),
                description=f"N {numero} - {type_marche}" if numero else type_marche,
                dedupe_key=f"marchespublics_ci|{numero or url}|{objet[:80]}",
            ))
        return items

    @staticmethod
    def _to_iso(date_str):
        if not date_str:
            return None
        m = DATE_RE.match(date_str.strip())
        if not m:
            return date_str
        d, mo, y = m.groups()
        if y == "-0001" or y == "0001":
            return None
        return f"{y}-{mo}-{d}"

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://marchespublics.ci" + ("" if href.startswith("/") else "/") + href
