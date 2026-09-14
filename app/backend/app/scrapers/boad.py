"""
Scraper BOAD (Banque Ouest Africaine de Developpement).

Depuis sept. 2026 le site est une application Laravel/Inertia : la page
/fr/opportunites/appels-doffre ne contient plus de cartes HTML, les avis sont
fournis en JSON dans l'attribut `data-page` de la racine de l'application
(props.tenders, pagination Laravel classique ?page=N, 6 avis par page).
Chaque avis porte un titre, un lien relatif, une date de publication et,
quand elle est renseignee, une plage acf.start_at / acf.end_at (JJ/MM/AAAA).
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

LISTING_URL = "https://www.boad.org/fr/opportunites/appels-doffre"
PAGES_TO_FETCH = 5
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
# Resultats, PV d'ouverture, plans de passation : pas des opportunites a saisir.
NOT_AN_OPPORTUNITY_RE = re.compile(
    r"^\s*(r[ée]sultats?|pv d|proc[eè]s[- ]verbal|plan de passation|avis d.attribution)", re.I)


class BoadScraper(BaseScraper):
    source_id = "boad"
    source_name = "BOAD"
    source_url = "https://www.boad.org/fr"
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        seen: set[str] = set()
        for page in range(1, PAGES_TO_FETCH + 1):
            url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
            try:
                # pages lourdes (~500 Ko) et serveur lent
                resp = self.get(url, timeout=45)
            except Exception:
                if page == 1:
                    raise
                break  # on garde les avis des pages deja lues
            tenders = self._tenders_payload(resp.text)
            if tenders is None:
                if page == 1:
                    # Structure du site modifiee : on le signale au lieu de
                    # renvoyer silencieusement 0 avis.
                    raise RuntimeError("Structure de la page BOAD inattendue (attribut data-page absent).")
                break

            for row in tenders.get("data") or []:
                item = self._to_item(row)
                if item and item.url not in seen:
                    seen.add(item.url)
                    items.append(item)

            if not tenders.get("next_page_url"):
                break
        return items

    @staticmethod
    def _tenders_payload(html: str):
        soup = BeautifulSoup(html, "html.parser")
        root = soup.find(attrs={"data-page": True})
        if root is None:
            return None
        try:
            return json.loads(root["data-page"])["props"]["tenders"]
        except (ValueError, KeyError, TypeError):
            return None

    def _to_item(self, row: dict) -> TenderItem | None:
        title = self.clean_text(row.get("title"))
        link = row.get("link")
        if not title or not link or NOT_AN_OPPORTUNITY_RE.match(title):
            return None

        acf = row.get("acf") or {}
        published = self._to_iso(acf.get("start_at")) or (row.get("date_gmt") or "")[:10] or None
        deadline = self._to_iso(acf.get("end_at"))
        presentation = (acf.get("presentation") or {}).get("text") or ""
        description = self.clean_text(BeautifulSoup(presentation, "html.parser").get_text(" ")) if presentation else None
        country, zone = self.guess_country_zone(title, self.default_zone)

        return TenderItem(
            title=title,
            url=self._absolute(link),
            source_id=self.source_id,
            source_name=self.source_name,
            zone=zone,
            entity="BOAD",
            category=self.guess_category(title),
            country=country,
            published_date=published,
            deadline_date=deadline,
            description=description,
            # meme cle qu'avant la refonte du site : pas de doublons en base
            dedupe_key=f"boad|{link}",
        )

    @staticmethod
    def _to_iso(date_str):
        if not date_str:
            return None
        m = DATE_RE.match(str(date_str).strip())
        if not m:
            return None
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d}"

    @staticmethod
    def _absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.boad.org" + ("" if href.startswith("/") else "/") + href
