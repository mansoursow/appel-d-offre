"""
Scraper SenOffre (senoffre.com) - plateforme d'appels d'offres du Senegal.

Structure observee sur la page d'accueil / latest-jobs : pour chaque offre,
un bloc contenant :
  - un lien <h5><a>NomEntreprise</a></h5>
  - un lien <h3><a href=".../slug-ID">Titre</a></h3>
  - une meta-ligne : date (YYYY-MM-DD), lien categorie (/category/..),
    lien localite (/jobs/ville/id), type ("Appel d'offre" ou
    "Avis à manifestation d'intérêt (AMI)")
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

BASE_URL = "https://senoffre.com"
LISTING_URL = "https://senoffre.com/latest-jobs"

DETAIL_HREF_RE = re.compile(r"-\d+/?$")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
TYPE_RE = re.compile(r"(Avis\s*à\s*manifestation\s*d.?int[ée]r[êe]t[^\n]*|Appel\s*d.?offre[^\n]*|Demande\s*de\s*prix[^\n]*)", re.I)


class SenOffreScraper(BaseScraper):
    source_id = "senoffre"
    source_name = "Sen Offre"
    source_url = "https://senoffre.com/"
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        for url in (LISTING_URL, self.source_url):
            try:
                resp = self.get(url)
            except Exception:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            items.extend(self._parse(soup))
            if items:
                break
        seen = set()
        unique = []
        for it in items:
            if it.url in seen:
                continue
            seen.add(it.url)
            unique.append(it)
        return unique

    def _parse(self, soup: BeautifulSoup) -> list[TenderItem]:
        results = []
        for h3 in soup.find_all("h3"):
            a = h3.find("a")
            if not a or not a.get("href"):
                continue
            href = a["href"]
            if not DETAIL_HREF_RE.search(href):
                continue
            title = self.clean_text(a.get_text())
            if not title:
                continue

            block = self.find_ancestor_with(
                h3, lambda el: DATE_RE.search(el.get_text(" ")) and TYPE_RE.search(el.get_text(" "))
            )
            block_text = self.clean_text(block.get_text(" ")) or ""

            h5 = h3.find_previous("h5")
            entity = self.clean_text(h5.get_text()) if h5 else None

            date_match = DATE_RE.search(block_text)
            type_match = TYPE_RE.search(block_text)

            category_link = block.find("a", href=re.compile(r"/category/"))
            location_link = block.find("a", href=re.compile(r"/jobs/"))

            type_text = type_match.group(1).strip() if type_match else ""
            category = self.guess_category(type_text or title)

            results.append(TenderItem(
                title=title,
                url=self._absolute(href),
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=entity,
                category=category,
                country="Senegal",
                published_date=date_match.group(1) if date_match else None,
                deadline_date=None,
                description=self.clean_text(
                    f"{category_link.get_text() if category_link else ''} - "
                    f"{location_link.get_text() if location_link else ''}"
                ),
                dedupe_key=f"senoffre|{href}",
            ))
        return results

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return BASE_URL.rstrip("/") + "/" + href.lstrip("/")
