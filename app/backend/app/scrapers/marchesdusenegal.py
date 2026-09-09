"""
Scraper Marches du Senegal (marchesdusenegal.com) - agregateur prive.

Page /tenders : cartes HTML avec
  - span.tender-source   : source d'origine (portail officiel, bailleurs, ...)
  - h3.tender-title      : titre (dans un lien /tenders/<slug>)
  - span.truncate        : autorite contractante
  - date en gras (badge) : date limite au format "9 Octobre 2025"
  - p.tender-desc        : "TYPE: ... SECTEUR: ..."

Interet : ce site agrege notamment marchespublics.sn (souvent en panne),
il sert donc de relais fiable pour les avis officiels senegalais.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

BASE_URL = "https://marchesdusenegal.com"
LISTING_URL = "https://marchesdusenegal.com/tenders"


class MarchesDuSenegalScraper(BaseScraper):
    source_id = "marchesdusenegal"
    source_name = "Marche du Senegal"
    source_url = "https://marchesdusenegal.com/"
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        resp = self.get(LISTING_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        items: list[TenderItem] = []
        seen: set[str] = set()
        for h3 in soup.find_all("h3", class_="tender-title"):
            a = h3.find("a") or h3.find_parent("a")
            if a is None:
                # le lien peut englober la carte : chercher autour
                card_link = h3.find_previous("a", href=re.compile(r"^/tenders/."))
                a = card_link
            href = a.get("href") if a else None
            title = self.clean_text(h3.get_text())
            if not title or not href or href in seen:
                continue
            seen.add(href)

            card = self.find_ancestor_with(
                h3, lambda el: el.find("p", class_="tender-desc") is not None
            )

            entity_el = card.find("span", class_="truncate")
            entity = self.clean_text(entity_el.get_text()) if entity_el else None

            desc_el = card.find("p", class_="tender-desc")
            desc = self.clean_text(desc_el.get_text()) if desc_el else None

            source_el = card.find("span", class_="tender-source")
            origin = self.clean_text(source_el.get_text()) if source_el else None
            if origin:
                desc = f"[via {origin}] {desc or ''}".strip()

            # date limite : badge "9 Octobre 2025" (parse generique en aval)
            deadline = None
            badge = card.find("div", class_=re.compile(r"font-bold"))
            if badge:
                m = re.search(r"\d{1,2}\s+\w+\s+\d{4}", badge.get_text())
                if m:
                    deadline = m.group(0)

            card_text = card.get_text(" ")
            country, zone = self.guess_country_zone(card_text, self.default_zone)

            items.append(TenderItem(
                title=title,
                url=BASE_URL + href if href.startswith("/") else href,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity=entity,
                category=self.guess_category(f"{title} {desc or ''}"),
                country=country or "Senegal",
                deadline_date=deadline,
                description=desc,
                dedupe_key=f"marchesdusenegal|{href}",
            ))
        return items
