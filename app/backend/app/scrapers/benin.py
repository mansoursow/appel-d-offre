"""
Scraper Benin - Portail national des marches publics (marches-publics.bj).

Le site est une application Angular ; les donnees viennent de l'API
publique https://api.marches-publics.bj/v2/api/portail/... (reponse
paginee Spring). La rubrique "avis d'appel a concurrence" du portail est
actuellement vide ; on remonte les AVIS GENERAUX de passation des marches
(numero, autorite contractante, date de publication, PDF de l'avis).

Certains libelles de la base ont ete encodes en cp850 ("UniversitÚ") :
on repare ce mojibake au mieux.
"""
from __future__ import annotations

from .base import BaseScraper, TenderItem

API_URL = ("https://api.marches-publics.bj/v2/api/portail/avisgeneraux"
           "?page=0&size=40&sort=id,desc")
PORTAL_URL = "https://marches-publics.bj/avis-generaux"


def _fix_mojibake(text: str | None) -> str | None:
    """Repare les chaines stockees en cp850 puis lues comme unicode."""
    if not text:
        return text
    try:
        fixed = text.encode("cp850").decode("cp1252")
        # heuristique : on garde la version corrigee si elle contient plus
        # de lettres accentuees francaises plausibles
        if sum(c in "éèêàâçîïôûùë" for c in fixed) > sum(c in "éèêàâçîïôûùë" for c in text):
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


class BeninScraper(BaseScraper):
    source_id = "benin"
    source_name = "Site officiel Benin"
    source_url = "https://marches-publics.bj/"
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        data = self.get(API_URL).json()
        items: list[TenderItem] = []
        for avis in data.get("content", []):
            avis_id = avis.get("id")
            numero = avis.get("numero") or ""
            ac = avis.get("autoriteContractante") or {}
            entity = self.clean_text(_fix_mojibake(ac.get("denomination")))
            if not avis_id:
                continue

            title = f"Avis general de passation des marches {avis.get('annee') or ''}".strip()
            if entity:
                title += f" - {entity}"

            url = avis.get("fichier_Avis") or PORTAL_URL

            items.append(TenderItem(
                title=title[:300],
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=entity,
                category="autre",
                country="Benin",
                published_date=avis.get("datepublication"),
                description=f"N {numero}" if numero else None,
                dedupe_key=f"benin|{avis_id}",
            ))
        return items
