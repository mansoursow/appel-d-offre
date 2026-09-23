"""
Scraper Senegal - Portail officiel des marches publics (marchespublics.sn).

Portail Joomla historique. La page d'accueil liste les derniers avis dans des
blocs <table> : chaque ligne <tr> contient "DD/MM/YYYY : Titre" avec un lien
vers le detail "index.php?option=com_loffres&task=txt&key=NNNNN".
La date affichee sur l'accueil est la DATE LIMITE de depot.

NB : le serveur est lent (14 a 18 s pour rendre la page d'accueil) et coupe
parfois la connexion. Le scraper laisse donc un delai large et reessaie ; en
cas d'echec l'erreur est remontee proprement par scraper_service sans casser
les autres sources. HTTPS est tente en premier mais echoue en general
(certificat), d'ou le repli HTTP.
"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup

from .base import BaseScraper, TenderItem

HTTP_URL = "http://www.marchespublics.sn/"
HTTPS_URL = "https://www.marchespublics.sn/"

# Le serveur met 14 a 18 s a repondre : delai large et plusieurs tentatives.
TIMEOUT = 75
TENTATIVES = 3

# Lien de detail d'un appel d'offres (&amp; deja decode par BeautifulSoup)
AO_HREF_RE = re.compile(r"option=com_loffres.*task=txt.*key=(\d+)")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class MarchesPublicsSNScraper(BaseScraper):
    source_id = "marchespublics_sn"
    source_name = "Marche public Senegal"
    source_url = HTTP_URL
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        resp = None
        last_exc = None
        for essai in range(TENTATIVES):
            for url in (HTTPS_URL, HTTP_URL):
                try:
                    resp = self.get(url, timeout=TIMEOUT)
                    break
                except Exception as exc:
                    last_exc = exc
            if resp is not None:
                break
            if essai < TENTATIVES - 1:
                time.sleep(3)
        if resp is None:
            raise RuntimeError(f"marchespublics.sn injoignable : {last_exc}")

        soup = BeautifulSoup(resp.text, "html.parser")
        items: list[TenderItem] = []
        seen_keys: set[str] = set()

        for a in soup.find_all("a", href=AO_HREF_RE):
            m = AO_HREF_RE.search(a["href"])
            key = m.group(1)
            if key in seen_keys:
                continue

            row = a.find_parent("tr") or a.parent
            row_text = self.clean_text(row.get_text(" ")) or ""

            date_m = DATE_RE.search(row_text)
            deadline = None
            if date_m:
                d, mo, y = date_m.groups()
                deadline = f"{y}-{mo}-{d}"

            # La ligne est de la forme "DD/MM/YYYY : Titre"
            title = re.sub(r"^\s*\d{2}/\d{2}/\d{4}\s*:?\s*", "", row_text).strip()
            if not title:
                title = self.clean_text(a.get_text()) or ""
            if not title:
                continue

            seen_keys.add(key)
            category = self.guess_category(title)
            if category == "autre":
                # Le bloc d'accueil parcouru ici ne contient que des appels
                # d'offres publies par le portail officiel.
                category = "appel_offre"

            items.append(TenderItem(
                title=title,
                url=f"{HTTP_URL}index.php?option=com_loffres&task=txt&key={key}&Itemid=104",
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                category=category,
                country="Senegal",
                deadline_date=deadline,
                dedupe_key=f"marchespublics_sn|{key}",
            ))
        return items
