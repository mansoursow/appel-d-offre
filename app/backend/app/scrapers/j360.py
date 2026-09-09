"""
Scraper J360 (j360.info) - agregateur d'appels d'offres Afrique/international.

Le site est protege par Anubis (anti-bot par preuve de travail) qui ne
challenge que les User-Agent contenant "Mozilla" : on utilise donc un
User-Agent d'outil, ce qui passe sans challenge.

Page /appels-d-offres/afrique/senegal/ : cartes div.card-body avec
  - div.card-title (lien /appels-d-offres/<id>-<slug>/)
  - "Localisation <Pays>"
  - date limite DD/MM/YYYY
"""
from __future__ import annotations

import re

import requests

from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT
from .base import BaseScraper, TenderItem

BASE_URL = "https://www.j360.info"
LISTING_URLS = [
    "https://www.j360.info/appels-d-offres/afrique/senegal/",
    "https://www.j360.info/appels-d-offres/",
]

# Surtout PAS un UA "Mozilla..." : Anubis challengerait la requete.
UA = {"User-Agent": "TenderWatch/1.0 (+veille marches publics)"}

DETAIL_RE = re.compile(r"/appels-d-offres/(\d{5,})[-/]")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class J360Scraper(BaseScraper):
    source_id = "j360"
    source_name = "J360"
    source_url = "https://www.j360.info/"
    default_zone = "senegal"

    def get(self, url: str, **kwargs) -> requests.Response:
        resp = requests.get(url, headers=UA, timeout=REQUEST_TIMEOUT + 15, **kwargs)
        resp.raise_for_status()
        return resp

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        seen: set[str] = set()
        for url, zone in zip(LISTING_URLS, ("senegal", "international")):
            try:
                resp = self.get(url)
            except Exception:
                continue
            for item in self._parse(resp.text, zone):
                if item.dedupe_key in seen:
                    continue
                seen.add(item.dedupe_key)
                items.append(item)
        return items

    def _parse(self, html: str, fallback_zone: str) -> list[TenderItem]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for a in soup.find_all("a", href=DETAIL_RE):
            title = self.clean_text(a.get_text())
            if not title or len(title) < 15:
                continue
            tender_id = DETAIL_RE.search(a["href"]).group(1)

            card = self.find_ancestor_with(
                a, lambda el: "Localisation" in el.get_text()
            )
            card_text = " ".join(card.get_text(" ").split())

            deadline = None
            dm = DATE_RE.search(card_text)
            if dm:
                d, mo, y = dm.groups()
                deadline = f"{y}-{mo}-{d}"

            loc = None
            lm = re.search(r"Localisation\s+([A-Za-zÀ-ÿ' -]+?)(?:\s+Temps|$)", card_text)
            if lm:
                loc = self.clean_text(lm.group(1))
            country, zone = self.guess_country_zone(loc or card_text, fallback_zone)

            href = a["href"]
            results.append(TenderItem(
                title=title,
                url=href if href.startswith("http") else BASE_URL + href,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                category=self.guess_category(title),
                country=country or loc,
                deadline_date=deadline,
                dedupe_key=f"j360|{tender_id}",
            ))
        return results
