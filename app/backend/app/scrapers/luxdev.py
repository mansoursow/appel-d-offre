"""
Scraper LuxDev (luxdev.lu) - cooperation luxembourgeoise.

Page /fr/marches/avis-dappels-doffres : liens de detail
/fr/marches/avis-dappels-doffres/<slug> dont le texte commence par le
statut ("Ouvert" / "Cloture") suivi du pays puis du titre.
On y ajoute les appels a propositions (/fr/marches/appels-propositions).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

BASE_URL = "https://luxdev.lu"
LISTINGS = [
    ("https://luxdev.lu/fr/marches/avis-dappels-doffres", "appel_offre"),
    ("https://luxdev.lu/fr/marches/appels-propositions", "ami"),
]

STATUS_RE = re.compile(r"^(Ouvert|Clôturé|Cloture|Ferme|Fermé)\s+", re.I)


class LuxDevScraper(BaseScraper):
    source_id = "luxdev"
    source_name = "LuxDev"
    source_url = "https://luxdev.lu/fr"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        seen: set[str] = set()
        for listing_url, default_cat in LISTINGS:
            try:
                resp = self.get(listing_url)
            except Exception:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            path_prefix = listing_url.replace(BASE_URL, "")
            for a in soup.find_all("a", href=re.compile(re.escape(path_prefix) + r"/.+")):
                href = a["href"].split("?")[0]
                if href in seen:
                    continue
                raw = self.clean_text(a.get_text()) or ""
                if len(raw) < 20:
                    continue
                seen.add(href)

                status_m = STATUS_RE.match(raw)
                text = STATUS_RE.sub("", raw)
                closed = bool(status_m and "ouvert" not in status_m.group(1).lower())

                country, zone = self.guess_country_zone(text, self.default_zone)
                # retire le pays en tete du titre s'il y figure
                title = text
                if country:
                    title = re.sub(r"^[A-Za-zÀ-ÿ' -]{3,25}?\s{1,}", "", text, count=1) \
                        if text.lower().startswith(country.lower().split()[0]) else text
                title = title.strip() or text

                items.append(TenderItem(
                    title=title[:300],
                    url=href if href.startswith("http") else BASE_URL + href,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    zone=zone,
                    category=self.guess_category(title) if self.guess_category(title) != "autre" else default_cat,
                    country=country,
                    description=("Statut : clôturé" if closed else "Statut : ouvert"),
                    dedupe_key=f"luxdev|{href}",
                ))
        return items
