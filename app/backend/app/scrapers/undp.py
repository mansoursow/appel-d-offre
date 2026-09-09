"""
Scraper PNUD / UNDP (procurement-notices.undp.org).

Le site rend une table "responsive" ou chaque enregistrement apparait, une
fois le HTML transforme en texte, sous la forme repetee :
    Title / <valeur> / Ref No / <valeur> / UNDP Office/Country / <valeur> /
    Process / <valeur> / Deadline / <valeur> / Posted / <valeur>
(verifie en recuperant la page en direct). On s'appuie donc sur une extraction
texte par regex, robuste aux changements mineurs de mise en page, complete
par une tentative de recuperation des liens <a> pour pointer vers l'annonce
precise plutot que vers la page d'accueil.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..config import SOUS_REGION_COUNTRIES
from .base import BaseScraper, TenderItem

LISTING_URL = "https://procurement-notices.undp.org/"

RECORD_RE = re.compile(
    r"Title\s*(?P<title>.*?)\s*Ref No\s*(?P<ref_no>.*?)\s*"
    r"UNDP Office/Country\s*(?P<country>.*?)\s*"
    r"Process\s*(?P<process>.*?)\s*"
    r"Deadline\s*(?P<deadline>.*?)\s*"
    r"Posted\s*(?P<posted>.*?)"
    r"(?=Title\s|\Z)",
    re.S,
)


class UndpScraper(BaseScraper):
    source_id = "pnud"
    source_name = "PNUD - UNDP"
    source_url = LISTING_URL
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        resp = self.get(LISTING_URL)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text("\n")

        # Cherche les liens par titre pour retrouver l'URL exacte de l'annonce
        link_by_title = {}
        for a in soup.find_all("a"):
            label = self.clean_text(a.get_text())
            href = a.get("href")
            if label and href and len(label) > 8:
                link_by_title.setdefault(label, self._absolute(href))

        items: list[TenderItem] = []
        for m in RECORD_RE.finditer(text):
            title = self.clean_text(m.group("title"))
            country_text = self.clean_text(m.group("country")) or ""
            if not title or title.lower() == "title":
                continue

            # On ne garde que Senegal + pays UEMOA (le site liste des avis du monde entier)
            country, zone = self.guess_country_zone(country_text, self.default_zone)
            if not any(c.replace("'", "").lower() in country_text.replace("'", "").lower()
                       for c in SOUS_REGION_COUNTRIES):
                continue

            ref_no = self.clean_text(m.group("ref_no")) or ""
            process = self.clean_text(m.group("process")) or ""
            deadline = self.clean_text(m.group("deadline"))
            posted = self.clean_text(m.group("posted"))

            url = link_by_title.get(title, LISTING_URL)

            items.append(TenderItem(
                title=title,
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity=country_text or None,
                category=self.guess_category(f"{process} {title}"),
                country=country or country_text,
                published_date=posted,
                deadline_date=deadline,
                description=f"Ref: {ref_no} - {process}" if ref_no else process,
                dedupe_key=f"pnud|{ref_no or title}",
            ))
        return items

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        return LISTING_URL.rstrip("/") + "/" + href.lstrip("/")
