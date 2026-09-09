"""
Scraper AFD / DgMarket (afd.dgmarket.com) - avis finances par l'AFD.

Page /tenders/brandedNoticeList.do : table "Pays | Titre de l'Avis |
Publie | Date limite", lien de detail /tender/<id>.
Les dates sont au format "Jul 13, 2026" avec des abreviations de mois
parfois francisees ("Aou", "Fev", "Dec") qu'on normalise.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

BASE_URL = "https://afd.dgmarket.com"
LISTING_URL = "https://afd.dgmarket.com/tenders/brandedNoticeList.do"

MONTH_FIX = {
    "janv": "Jan", "fév": "Feb", "fev": "Feb", "avr": "Apr", "mai": "May",
    "juin": "Jun", "juil": "Jul", "aou": "Aug", "août": "Aug",
    "déc": "Dec", "dec": "Dec",
}


class DgMarketScraper(BaseScraper):
    source_id = "afd_dgmarket"
    source_name = "Cooperation internationale (AFD/DgMarket)"
    source_url = "https://afd.dgmarket.com/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        resp = self.get(LISTING_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        table = None
        for t in soup.find_all("table"):
            if "Titre de l" in t.get_text():
                table = t
        if table is None:
            return []

        items: list[TenderItem] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue
            link = tr.find("a", href=re.compile(r"/tender/\d+"))
            if link is None:
                continue
            country_txt = self.clean_text(cells[0].get_text())
            title = self.clean_text(link.get_text()) or self.clean_text(cells[1].get_text())
            published = self._fix_date(self.clean_text(cells[2].get_text()))
            deadline = self._fix_date(self.clean_text(cells[3].get_text()))
            if not title:
                continue

            href = link["href"]
            url = href if href.startswith("http") else BASE_URL + href
            country, zone = self.guess_country_zone(country_txt or "", self.default_zone)

            items.append(TenderItem(
                title=title,
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                category=self.guess_category(title) if self.guess_category(title) != "autre" else "appel_offre",
                country=country or country_txt,
                published_date=published,
                deadline_date=deadline,
                dedupe_key=f"dgmarket|{href}",
            ))
        return items

    @staticmethod
    def _fix_date(date_str):
        """Normalise "Aou 17, 2026" -> "Aug 17, 2026" pour dateutil."""
        if not date_str:
            return None
        lowered = date_str.lower()
        for fr, en in MONTH_FIX.items():
            if lowered.startswith(fr):
                return en + date_str[len(fr):]
        return date_str
