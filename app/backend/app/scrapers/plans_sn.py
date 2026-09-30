"""
Plans de passation des marches publics du Senegal (marchespublics.sn).

Chaque autorite contractante publie, en debut d'exercice, la liste de ce
qu'elle compte lancer dans l'annee : reference, objet, type de marche, mode de
passation, date prevue de lancement et date prevue d'attribution. C'est une
information d'anticipation : on sait des janvier ce qui sera mis en
concurrence, avant meme la parution de l'avis.

Le portail organise ces plans en trois niveaux :
  1. types d'autorite      index.php?option=com_plan&task=morepublic
  2. autorites d'un type   ...&task=frontgen&idtype=N
  3. plan d'une autorite   ...&task=detailautorite&idautorite=X&year=AAAA&idtype=N

Comme le reste du portail, ce n'est joignable que depuis le Senegal : la
collecte est faite par le relais local (collect_local.py).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date
from typing import Iterator, Optional

import requests
from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS

BASE_URL = "http://www.marchespublics.sn/"
TYPES_URL = BASE_URL + "index.php?option=com_plan&task=morepublic&Itemid=105"
TYPE_URL = BASE_URL + "index.php?option=com_plan&task=frontgen&idtype={idtype}&Itemid=105"
AUTORITE_URL = (BASE_URL + "index.php?option=com_plan&task=detailautorite"
                "&idautorite={idautorite}&year={annee}&idtype={idtype}&Itemid=105")

TIMEOUT = 180
TENTATIVES = 3
# Annee de gestion collectee (0 = celle en cours).
ANNEE = int(os.environ.get("MPSN_PLANS_ANNEE", "0")) or date.today().year

IDTYPE_RE = re.compile(r"idtype=(\d+)")
AUTORITE_RE = re.compile(r"idautorite=(\d+)")
DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


@dataclass
class PlanItem:
    """Une ligne de plan de passation."""

    reference: str
    objet: str
    type_marche: Optional[str]
    mode_passation: Optional[str]
    date_lancement: Optional[str]     # AAAA-MM-JJ
    date_attribution: Optional[str]   # AAAA-MM-JJ
    autorite: str
    type_autorite: str
    annee: int
    url: str
    dedupe_key: str


class PlansSenegalScraper:
    source_id = "plans_sn"
    source_name = "Plans de passation (Senegal)"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    # --- reseau ---

    def _get(self, url: str, obligatoire: bool = True) -> Optional[requests.Response]:
        derniere = None
        for essai in range(TENTATIVES):
            try:
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                if len(resp.content) > 3000:
                    return resp
                derniere = RuntimeError(f"reponse vide ({len(resp.content)} octets)")
            except Exception as exc:
                derniere = exc
            time.sleep(4)
        if obligatoire and derniere is not None:
            raise RuntimeError(f"{url} : {derniere}")
        return None

    @staticmethod
    def _soup(resp: requests.Response) -> BeautifulSoup:
        try:
            html = resp.content.decode("utf-8")
        except UnicodeDecodeError:
            html = resp.content.decode("cp1252", "replace")
        return BeautifulSoup(html, "html.parser")

    # --- parcours du portail ---

    def types_autorites(self) -> list[tuple[str, str]]:
        """[(idtype, libelle)] : Etat, collectivites locales, agences..."""
        soup = self._soup(self._get(TYPES_URL))
        vus: dict[str, str] = {}
        for a in soup.find_all("a", href=True):
            m = IDTYPE_RE.search(a["href"])
            libelle = (a.get_text(" ", strip=True) or "").strip()
            if m and libelle and m.group(1) not in vus:
                vus[m.group(1)] = libelle
        return list(vus.items())

    def autorites(self, idtype: str) -> list[tuple[str, str, int]]:
        """[(idautorite, nom, annee)] pour un type d'autorite."""
        soup = self._soup(self._get(TYPE_URL.format(idtype=idtype)))
        vus: dict[str, tuple[str, str, int]] = {}
        for a in soup.find_all("a", href=True):
            m = AUTORITE_RE.search(a["href"])
            if not m:
                continue
            ligne = a.find_parent("tr")
            if ligne is None:
                continue
            cellules = [c.get_text(" ", strip=True) for c in ligne.find_all("td")]
            cellules = [c for c in cellules if c]
            if len(cellules) < 2:
                continue
            nom = cellules[0]
            annee = next((int(c) for c in cellules[1:] if c.isdigit() and len(c) == 4), ANNEE)
            vus.setdefault(m.group(1), (m.group(1), nom, annee))
        return list(vus.values())

    def plan(self, idtype: str, type_libelle: str, idautorite: str, nom: str, annee: int) -> list[PlanItem]:
        """Les realisations envisagees par une autorite pour une annee."""
        url = AUTORITE_URL.format(idautorite=idautorite, annee=annee, idtype=idtype)
        resp = self._get(url, obligatoire=False)
        if resp is None:
            return []
        soup = self._soup(resp)
        items: list[PlanItem] = []
        for tr in soup.find_all("tr"):
            cellules = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            # Les lignes de plan ont exactement 7 cellules, la derniere vide.
            if len(cellules) != 7:
                continue
            reference, objet, type_marche, mode, lancement, attribution, _ = cellules
            if not reference or not objet or not DATE_RE.match(lancement or ""):
                continue
            items.append(PlanItem(
                reference=reference[:80],
                objet=objet[:500],
                type_marche=type_marche or None,
                mode_passation=mode or None,
                date_lancement=self._to_iso(lancement),
                date_attribution=self._to_iso(attribution),
                autorite=nom[:250],
                type_autorite=type_libelle[:120],
                annee=annee,
                url=url,
                dedupe_key=f"plan_sn|{annee}|{idautorite}|{reference}",
            ))
        return items

    def parcourir(self, annee: int | None = None) -> Iterator[tuple[str, list[PlanItem]]]:
        """Parcourt tout le portail, une autorite a la fois : le relais peut
        ainsi afficher l'avancement et reprendre apres une coupure."""
        annee = annee or ANNEE
        for idtype, libelle in self.types_autorites():
            for idautorite, nom, annee_pub in self.autorites(idtype):
                yield nom, self.plan(idtype, libelle, idautorite, nom, annee_pub or annee)

    @staticmethod
    def _to_iso(valeur: str | None) -> Optional[str]:
        m = DATE_RE.match((valeur or "").strip())
        if not m:
            return None
        jour, mois, an = m.groups()
        return f"{an}-{mois}-{jour}"
