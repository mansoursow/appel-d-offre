"""
Classes/utilitaires communs a tous les scrapers.

Chaque scraper concret doit :
  1. Heriter de BaseScraper
  2. Definir source_id / source_name / source_url / default_zone
  3. Implementer fetch() -> list[TenderItem]

Le reste (dedoublonnage, insertion en base, gestion des erreurs) est gere
de maniere generique par scraper_service.py, pour que l'ajout d'une nouvelle
source ne demande JAMAIS de toucher au reste de l'application.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import requests

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT, SOUS_REGION_COUNTRIES


@dataclass
class TenderItem:
    title: str
    url: str
    source_id: str
    source_name: str
    zone: str                      # senegal | uemoa | international
    entity: Optional[str] = None
    category: Optional[str] = None  # appel_offre | ami | autre
    country: Optional[str] = None
    published_date: Optional[str] = None
    deadline_date: Optional[str] = None
    description: Optional[str] = None
    dedupe_key: str = field(default="")

    def __post_init__(self):
        if not self.dedupe_key:
            base = f"{self.source_id}|{self.url or self.title}"
            self.dedupe_key = hashlib.sha256(base.encode("utf-8")).hexdigest()


class BaseScraper:
    source_id: str = ""
    source_name: str = ""
    source_url: str = ""
    default_zone: str = "international"

    def get(self, url: str, **kwargs) -> requests.Response:
        headers = {**DEFAULT_HEADERS, **kwargs.pop("headers", {})}
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp

    def fetch(self) -> list[TenderItem]:  # pragma: no cover - a redefinir
        raise NotImplementedError

    # --- helpers partages ---

    @staticmethod
    def guess_category(text: str) -> str:
        if not text:
            return "autre"
        t = text.lower()
        if "manifestation" in t or re.search(r"\bami\b", t):
            return "ami"
        if "appel d" in t or "appel a candidature" in t or "invitation to bid" in t or re.search(r"\brfp\b|\brfq\b", t):
            return "appel_offre"
        return "autre"

    @staticmethod
    def guess_country_zone(text: str, fallback_zone: str) -> tuple[Optional[str], str]:
        """Essaie de deviner pays + zone (senegal/uemoa/international) a partir d'un texte libre."""
        if not text:
            return None, fallback_zone
        t = text.lower()
        if "senegal" in t or "sénégal" in t:
            return "Senegal", "senegal"
        for country in SOUS_REGION_COUNTRIES:
            # \b évite les faux positifs type "Niger" dans "Nigeria"
            if re.search(r"\b" + re.escape(country.lower()) + r"\b", t):
                return country, "uemoa"
        return None, fallback_zone

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        return re.sub(r"\s+", " ", text).strip() or None

    @staticmethod
    def find_ancestor_with(tag, predicate, max_levels: int = 6):
        """Remonte l'arbre DOM depuis `tag` jusqu'a trouver un ancetre dont le
        texte satisfait `predicate` (ex: contient une date). Plus robuste
        qu'un nombre fixe de niveaux car la profondeur de nesting HTML reelle
        n'est pas toujours connue a l'avance."""
        node = tag
        best = tag
        for _ in range(max_levels):
            if node.parent is None:
                break
            node = node.parent
            best = node
            try:
                if predicate(node):
                    return node
            except Exception:
                continue
        return best
