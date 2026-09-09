"""
Scraper PLACE (marches-publics.gouv.fr) - plateforme des achats de l'Etat
francais, ou publient Expertise France et les operateurs francais.

Page ?page=Entreprise.EntrepriseAdvancedSearch&AllCons : blocs
div.item_consultation avec cons_procedure, cons_categorie, date limite
(div.day / div.month / div.year), cons_intitule "REF | Titre" et
"Objet : ...". Les liens de detail sont en JavaScript : on renvoie vers
la page de recherche.
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

LISTING_URL = ("https://www.marches-publics.gouv.fr/"
               "?page=Entreprise.EntrepriseAdvancedSearch&AllCons")

MONTHS = {
    "jan": "01", "fév": "02", "fev": "02", "mar": "03", "avr": "04",
    "mai": "05", "juin": "06", "juil": "07", "aoû": "08", "aou": "08",
    "sep": "09", "oct": "10", "nov": "11", "déc": "12", "dec": "12",
}


class ExpertiseFranceScraper(BaseScraper):
    source_id = "expertise_france"
    source_name = "Expertise France"
    source_url = LISTING_URL
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        sess = requests.Session()
        sess.headers.update(DEFAULT_HEADERS)
        resp = sess.get(LISTING_URL, timeout=REQUEST_TIMEOUT + 20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items: list[TenderItem] = []
        for block in soup.find_all("div", class_="item_consultation"):
            intitule_el = block.find("div", class_="cons_intitule") \
                or block.find("div", class_="identification_consultation")
            if intitule_el is None:
                continue
            intitule = self.clean_text(intitule_el.get_text()) or ""
            # "REF | Titre ... Objet : description"
            objet = None
            m = re.search(r"Objet\s*:\s*(.+)", intitule)
            if m:
                objet = m.group(1).strip()
                intitule = intitule[:m.start()].strip()
            ref, _, title = intitule.partition("|")
            ref = ref.strip()
            title = title.strip() or intitule

            proc_el = block.find("div", class_="cons_procedure")
            cat_el = block.find("div", class_="cons_categorie")
            procedure = self.clean_text(proc_el.get_text()) if proc_el else None
            categorie = self.clean_text(cat_el.get_text()) if cat_el else None

            deadline = self._extract_date(block)

            if not title:
                continue
            items.append(TenderItem(
                title=title[:300],
                url=LISTING_URL,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                category="appel_offre",
                country="France",
                deadline_date=deadline,
                description=self.clean_text(
                    f"{procedure or ''} {categorie or ''} - {(objet or '')[:250]}"),
                dedupe_key=f"place|{ref or title[:80]}",
            ))
        return items

    @staticmethod
    def _extract_date(block) -> str | None:
        day = block.find("div", class_="day")
        month = block.find("div", class_="month")
        year = block.find("div", class_="year")
        if not (day and month and year):
            return None
        d = day.get_text(strip=True)
        m_txt = month.get_text(strip=True).lower().rstrip(".")
        y = year.get_text(strip=True)
        for prefix, num in MONTHS.items():
            if m_txt.startswith(prefix):
                return f"{y}-{num}-{d.zfill(2)}"
        return None
