"""
Scraper AICS Dakar (dakar.aics.gov.it) - cooperation italienne.

Le site est un WordPress ; les avis de gara sont publies de facon
irreguliere (page "avvisi di gara enti terzi" + articles). On interroge
l'API REST WordPress par mots-cles et on parse la page des avvisi.
Il est normal que cette source renvoie 0 element une bonne partie de
l'annee : elle remonte les avis quand l'AICS en publie.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

WP_SEARCH = ("https://dakar.aics.gov.it/wp-json/wp/v2/posts"
             "?per_page=20&orderby=date&order=desc&search={kw}")
KEYWORDS = ["avviso", "bando", "manifestazione", "appel"]
AVVISI_PAGE = "https://dakar.aics.gov.it/aics/avvisi-di-gara-enti-terzi/"

TAG_RE = re.compile(r"<[^>]+>")


class AicsDakarScraper(BaseScraper):
    source_id = "aics_dakar"
    source_name = "AICS Dakar"
    source_url = "https://dakar.aics.gov.it/"
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        seen: set[str] = set()

        for kw in KEYWORDS:
            try:
                posts = self.get(WP_SEARCH.format(kw=kw)).json()
            except Exception:
                continue
            for post in posts:
                link = post.get("link")
                if not link or link in seen:
                    continue
                seen.add(link)
                title = self.clean_text(
                    TAG_RE.sub(" ", post.get("title", {}).get("rendered", "")))
                if not title:
                    continue
                country, zone = self.guess_country_zone(title, self.default_zone)
                items.append(TenderItem(
                    title=title,
                    url=link,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    zone=zone,
                    entity="AICS",
                    category=self.guess_category(title),
                    country=country or "Senegal",
                    published_date=(post.get("date") or "")[:10] or None,
                    dedupe_key=f"aics|{post.get('id') or link}",
                ))

        # Page "avvisi di gara enti terzi" : liens PDF / articles d'avis
        try:
            resp = self.get(AVVISI_PAGE)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                text = self.clean_text(a.get_text()) or ""
                href = a["href"]
                if len(text) < 25 or href in seen:
                    continue
                if not re.search(r"avvis|band|gara|manifestazion|appel", (text + href).lower()):
                    continue
                if re.search(r"/aics/(struttura|partnerships|profilo|titolare|cooperazione)", href):
                    continue
                seen.add(href)
                country, zone = self.guess_country_zone(text, self.default_zone)
                items.append(TenderItem(
                    title=text[:300],
                    url=href,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    zone=zone,
                    entity="AICS",
                    category=self.guess_category(text),
                    country=country or "Senegal",
                    dedupe_key=f"aics|{href}",
                ))
        except Exception:
            pass

        return items
