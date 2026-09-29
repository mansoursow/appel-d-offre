"""
Scraper Senegal - Portail officiel des marches publics (marchespublics.sn).

C'est le portail ou passent tous les appels d'offres et AMI de l'Etat, des
collectivites et des societes nationales : on cherche donc a en capter le
maximum.

Trois pistes ont ete essayees (28-29/09/2026) :
  - page d'accueil : seulement les 10 derniers avis ;
  - listes par type (task=ltype) : marche pour les prestations
    intellectuelles, mais le serveur renvoie une erreur 500 sur les
    categories volumineuses (Travaux, Fournitures) ;
  - RECHERCHE AVANCEE (retenue) : un POST renvoie toutes les categories a la
    fois, filtrees par periode de publication. 2 167 avis sur 12 mois,
    21 422 sur tout l'historique. Les dates doivent etre au format AAAA-MM-JJ
    (le format JJ/MM/AAAA affiche par le site ne renvoie aucun resultat).

Le tableau de resultats donne : reference, objet, autorite contractante,
date de publication, date limite de depot.

NB : le site n'accepte que les connexions venant du Senegal et met 15 a 30 s a
repondre. Il est donc interroge par le relais local (collect_local.py) depuis
un poste a Dakar, pas par le serveur.
"""
from __future__ import annotations

import os
import re
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS
from .base import BaseScraper, TenderItem

BASE_URL = "http://www.marchespublics.sn/"
SEARCH_URL = BASE_URL + "index.php?option=com_soffres&task=doadvancesearch&Itemid=143"

# Le serveur est lent (15 a 30 s) et coupe regulierement : delai large et
# plusieurs tentatives.
TIMEOUT = 300
TENTATIVES = 4

# Profondeur de collecte, en jours. 0 = tout l'historique (21 000 avis).
JOURS_COLLECTES = int(os.environ.get("MPSN_JOURS", "365"))

MARKET_RE = re.compile(r"task=moffres[^\"']*idmarket=(\d+)")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


class MarchesPublicsSNScraper(BaseScraper):
    source_id = "marchespublics_sn"
    source_name = "Marche public Senegal"
    source_url = BASE_URL
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)

        # Une premiere visite de l'accueil ouvre la session PHP attendue par
        # la recherche ; son echec n'est pas bloquant.
        self._request(session, "get", BASE_URL, obligatoire=False)

        debut = ""
        if JOURS_COLLECTES > 0:
            debut = (date.today() - timedelta(days=JOURS_COLLECTES)).isoformat()
        resp = self._request(session, "post", SEARCH_URL, data={
            "keywords": "",
            "bailleurs": "0",
            "typeavis": "0",       # toutes les categories
            "typeautorite": "0",
            "doit": "search",
            "lebouton2": "Rechercher",
            "debutpublication": debut,
            "finpublication": date.today().isoformat(),
        })
        if resp is None:
            raise RuntimeError("marchespublics.sn injoignable (recherche avancee sans reponse).")

        return self._parse(self._decode(resp.content))

    # --- reseau ---

    def _request(self, session, methode: str, url: str, obligatoire: bool = True, **kwargs):
        derniere = None
        for essai in range(TENTATIVES):
            try:
                resp = session.request(methode, url, timeout=TIMEOUT, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                derniere = exc
                if essai < TENTATIVES - 1:
                    time.sleep(5)
        if obligatoire and derniere is not None:
            raise RuntimeError(f"marchespublics.sn injoignable : {derniere}")
        return None

    @staticmethod
    def _decode(contenu: bytes) -> str:
        """Le portail melange UTF-8 et Windows-1252 selon les pages."""
        try:
            return contenu.decode("utf-8")
        except UnicodeDecodeError:
            return contenu.decode("cp1252", "replace")

    # --- lecture du tableau de resultats ---

    def _parse(self, html: str) -> list[TenderItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[TenderItem] = []
        vus: set[str] = set()

        for lien in soup.find_all("a", href=True):
            m = MARKET_RE.search(lien["href"])
            if not m:
                continue
            idmarket = m.group(1)
            ligne = lien.find_parent("tr")
            if ligne is None or idmarket in vus:
                continue
            cellules = [self.clean_text(c.get_text(" ")) or "" for c in ligne.find_all("td")]
            if len(cellules) < 5:
                continue
            reference, objet, autorite, publie, limite = cellules[:5]
            if not objet:
                continue
            vus.add(idmarket)

            published = self._to_iso(publie)
            deadline = self._to_iso(limite)
            # Le portail contient des dates saisies a l'envers (limite avant
            # publication, annees 2033...). Une date limite anterieure a la
            # publication est ignoree : l'avis reste visible au lieu d'etre
            # masque comme expire a tort.
            if published and deadline and deadline < published:
                deadline = None

            category = self.guess_category(objet)
            if category == "autre":
                category = "appel_offre"

            items.append(TenderItem(
                title=objet[:300],
                url=BASE_URL + lien["href"].lstrip("/"),
                source_id=self.source_id,
                source_name=self.source_name,
                zone=self.default_zone,
                entity=autorite or None,
                category=category,
                country="Senegal",
                published_date=published,
                deadline_date=deadline,
                description=f"Réf. {reference}" if reference else None,
                dedupe_key=f"marchespublics_sn|m{idmarket}",
            ))
        return items

    @staticmethod
    def _to_iso(valeur: str | None) -> str | None:
        m = DATE_RE.match((valeur or "").strip())
        if not m:
            return None
        jour, mois, annee = m.groups()
        return f"{annee}-{mois}-{jour}"
