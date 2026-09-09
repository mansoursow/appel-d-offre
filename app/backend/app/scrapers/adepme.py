"""
Scraper Senegal PME / ADEPME (marches.senegalpme.sn).

Pages "Appels d'offres" et "Marches publics" : blocs de consultation avec
libelles "Ref / Objet / Autorite contractante / Mode de passation /
Date de lancement / Date limite". Le detail complet est derriere un login,
mais toutes les infos utiles figurent deja sur la page publique.

NB : le certificat SSL du site est invalide -> verify=False assume.
"""
from __future__ import annotations

import re

import requests
import urllib3
from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

PAGES = [
    "https://marches.senegalpme.sn/appels-doffres/",
    "https://marches.senegalpme.sn/marches-publics/",
]

FIELD_RE = re.compile(
    r"Ref\s*(?P<ref>.*?)\s*Objet\s*(?P<objet>.*?)\s*Autorit[ée] contractante\s*(?P<entite>.*?)\s*"
    r"Mode de passation\s*(?P<mode>.*?)\s*Date de lancement\s*(?P<lancement>[\d-]*)\s*"
    r"(?:Date limite\s*(?P<limite>[\d-]*)|Date d'attribution\s*(?P<attribution>[\d-]*))",
    re.S,
)
DATE_RE = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")


class AdepmeScraper(BaseScraper):
    source_id = "adepme"
    source_name = "Senegal PME (ADEPME)"
    source_url = "https://marches.senegalpme.sn/"
    default_zone = "senegal"

    def get(self, url: str, **kwargs) -> requests.Response:
        headers = {**DEFAULT_HEADERS, **kwargs.pop("headers", {})}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT,
                            verify=False, **kwargs)
        resp.raise_for_status()
        return resp

    def fetch(self) -> list[TenderItem]:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        items: list[TenderItem] = []
        seen: set[str] = set()
        for page in PAGES:
            try:
                resp = self.get(page)
            except Exception:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for block_text in self._consultation_blocks(soup):
                m = FIELD_RE.search(block_text)
                if not m:
                    continue
                objet = self.clean_text(m.group("objet"))
                if not objet:
                    continue
                ref = self.clean_text(m.group("ref"))
                key = f"adepme|{ref or ''}|{objet[:80]}"
                if key in seen:
                    continue
                seen.add(key)

                mode = self.clean_text(m.group("mode")) or ""
                category = self.guess_category(f"{mode} {objet}")
                if category == "autre" and "offre" in mode.lower():
                    category = "appel_offre"

                items.append(TenderItem(
                    title=objet,
                    url=page,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    zone=self.default_zone,
                    entity=self.clean_text(m.group("entite")),
                    category=category,
                    country="Senegal",
                    published_date=self._to_iso(m.group("lancement")),
                    deadline_date=self._to_iso(m.group("limite")),
                    description=f"Ref {ref} - {mode}" if ref else mode,
                    dedupe_key=key,
                ))
        return items

    @staticmethod
    def _consultation_blocks(soup: BeautifulSoup) -> list[str]:
        """Isole le texte de chaque bloc de consultation (un bloc contient
        les libelles Ref/Objet/...)."""
        blocks = []
        for h4 in soup.find_all("h4"):
            if h4.get_text(strip=True) != "Ref":
                continue
            node = h4
            for _ in range(6):
                if node.parent is None:
                    break
                node = node.parent
                text = " ".join(node.get_text(" ").split())
                if "Objet" in text and "Autorit" in text:
                    blocks.append(text)
                    break
        return blocks

    @staticmethod
    def _to_iso(date_str):
        if not date_str:
            return None
        m = DATE_RE.match(date_str.strip())
        if not m:
            return date_str
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"
