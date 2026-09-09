"""
Scraper Mali Pages (malipages.com) - avis d'appels d'offres au Mali.

Page WordPress classique : chaque annonce a un lien de detail du type
https://www.malipages.com/appel-offre/<slug>/ (singulier, different de la
page de listing /avis-appels-offres/ qui est au pluriel). On s'appuie sur ce
motif d'URL pour reperer chaque bloc-annonce de maniere fiable.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

LISTING_URL = "https://www.malipages.com/avis-appels-offres/"
DETAIL_RE = re.compile(r"^https://www\.malipages\.com/appel-offre/[^/]+/?$")
PUBLISHED_RE = re.compile(r"Publi[ée]\s*le\s*(\d{2}/\d{2}/\d{4})", re.I)
DEADLINE_RE = re.compile(r"Candidatez avant le\s*(\d{2}/\d{2}/\d{4})", re.I)
PAGES_TO_FETCH = 3


class MalipagesScraper(BaseScraper):
    source_id = "malipages"
    source_name = "Mali Pages"
    source_url = LISTING_URL
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        seen_urls = set()
        for page in range(1, PAGES_TO_FETCH + 1):
            url = LISTING_URL if page == 1 else f"{LISTING_URL}page/{page}/"
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
                if it.url in seen_urls:
                    continue
                seen_urls.add(it.url)
                items.append(it)
                new_count += 1
            if new_count == 0:
                break
        return items

    def _parse(self, soup: BeautifulSoup) -> list[TenderItem]:
        results = []
        anchors = [a for a in soup.find_all("a", href=True) if DETAIL_RE.match(a["href"])]
        seen_href = set()
        for a in anchors:
            href = a["href"]
            title = self.clean_text(a.get_text())
            if href in seen_href or not title:
                continue
            seen_href.add(href)

            block = self.find_ancestor_with(a, lambda el: PUBLISHED_RE.search(el.get_text(" ")))
            block_text = self.clean_text(block.get_text(" ")) or ""

            company_link = block.find("a", href=re.compile(r"[?&]company="))
            category_links = block.find_all("a", href=re.compile(r"/appels-offres/"))
            category_text = " ".join(self.clean_text(c.get_text()) or "" for c in category_links)

            pub_match = PUBLISHED_RE.search(block_text)
            deadline_match = DEADLINE_RE.search(block_text)

            results.append(TenderItem(
                title=title,
                url=href,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=self.clean_text(company_link.get_text()) if company_link else None,
                category=self.guess_category(category_text or title),
                country="Mali",
                published_date=self._to_iso(pub_match.group(1)) if pub_match else None,
                deadline_date=self._to_iso(deadline_match.group(1)) if deadline_match else None,
                description=category_text or None,
                dedupe_key=f"malipages|{href}",
            ))
        return results

    @staticmethod
    def _to_iso(date_fr: str):
        try:
            d, m, y = date_fr.split("/")
            return f"{y}-{m}-{d}"
        except Exception:
            return date_fr
