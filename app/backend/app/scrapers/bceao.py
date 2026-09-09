"""
Scraper BCEAO - page "Marches publics et Achats".

Chaque avis apparait comme un lien dont le texte concatene :
"Publie le <date> <ref optionnelle> Date limite le <date> <titre>"
On filtre les liens via un motif regex plutot que via la structure DOM
(plus robuste, la page melangeant sections "En cours" et "Clos").
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

LISTING_URL = "https://www.bceao.int/fr/appels-offres/appels-offres-marches-publics-achats"
PAGES_TO_FETCH = 2

ITEM_RE = re.compile(
    r"Publi[ée]\s*le\s*(?P<pub>\d{1,2}\s+[^\d]+?\d{4})\s+"
    r"(?:(?P<ref>.*?)\s+)?"
    r"Date limite le\s*(?P<deadline>\d{1,2}\s+[^\d]+?\d{4})\s+"
    r"(?P<title>.+)",
    re.I,
)

MONTHS_FR = {
    "janvier": "01", "février": "02", "fevrier": "02", "mars": "03", "avril": "04", "mai": "05", "juin": "06",
    "juillet": "07", "août": "08", "aout": "08", "septembre": "09", "octobre": "10", "novembre": "11",
    "décembre": "12", "decembre": "12",
}


class BceaoScraper(BaseScraper):
    source_id = "bceao"
    source_name = "BCEAO"
    source_url = "https://www.bceao.int"
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
            if "/appels-offres/" not in a["href"]:
                continue
            text = self.clean_text(a.get_text())
            if not text:
                continue
            m = ITEM_RE.match(text)
            if not m:
                continue
            title = m.group("title").strip()
            country, zone = self.guess_country_zone(title, self.default_zone)
            results.append(TenderItem(
                title=title,
                url=self._absolute(a["href"]),
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="BCEAO",
                category=self.guess_category(title),
                country=country,
                published_date=self._to_iso(m.group("pub")),
                deadline_date=self._to_iso(m.group("deadline")),
                description=m.group("ref").strip() if m.group("ref") else None,
                dedupe_key=f"bceao|{a['href']}",
            ))
        return results

    @staticmethod
    def _to_iso(date_str):
        if not date_str:
            return None
        parts = date_str.strip().split()
        if len(parts) != 3:
            return date_str
        day, month, year = parts
        month_num = MONTHS_FR.get(month.lower())
        if not month_num:
            return date_str
        return f"{year}-{month_num}-{day.zfill(2)}"

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.bceao.int" + ("" if href.startswith("/") else "/") + href
