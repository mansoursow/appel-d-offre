"""
Module LinkedIn "via Google" (Google dorking), comme demande par l'utilisateur :

    site:linkedin.com/posts "appel d'offres OR Avis a manifestation d'interet"
    AND ("Senegal" OR "Cote d'Ivoire" ...)

Plutot que de scraper LinkedIn directement (bloque tres vite) ou de scraper
directement google.com/search (bloque tres vite aussi : CAPTCHA, IP ban), on
interroge un moteur de recherche via une methode qui ne se fait pas bloquer,
et on recupere les URLs de posts LinkedIn pertinents + le snippet affiche.

Quatre providers possibles, dans cet ordre de preference :
  1. Serper.dev            (SERPER_API_KEY)              - vrais resultats Google, tres fiable, payant (~1000 recherches/mois gratuites a l'inscription)
  2. SerpApi                (SERPAPI_API_KEY)             - vrais resultats Google, tres fiable, payant
  3. Google Programmable Search Engine / Custom Search API (GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID)
                                                            - OFFICIEL Google, gratuit jusqu'a 100 requetes/jour
  4. DuckDuckGo HTML        (aucune cle)                  - fallback gratuit mais moins riche/quotas incertains

Pour brancher une cle plus tard : definir les variables d'environnement
correspondantes avant de lancer le serveur (voir README.md, section LinkedIn).
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlparse, parse_qs

import requests

from ..config import (
    DEFAULT_HEADERS, REQUEST_TIMEOUT,
    SERPER_API_KEY, SERPAPI_API_KEY, GOOGLE_CSE_API_KEY, GOOGLE_CSE_ID,
)
from .base import BaseScraper, TenderItem

COUNTRIES_QUERY = '("Senegal" OR "Sénégal" OR "Côte d\'Ivoire" OR "Mali" OR "Burkina Faso" OR "Bénin" OR "Togo" OR "Niger")'
SEARCH_QUERY = f'site:linkedin.com/posts ("appel d\'offres" OR "avis a manifestation d\'interet" OR "AMI") AND {COUNTRIES_QUERY}'


class LinkedInGoogleScraper(BaseScraper):
    source_id = "linkedin"
    source_name = "LinkedIn (recherche Google)"
    source_url = "https://www.linkedin.com/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        if SERPER_API_KEY:
            raw = self._search_serper()
        elif SERPAPI_API_KEY:
            raw = self._search_serpapi()
        elif GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID:
            raw = self._search_google_cse()
        else:
            raw = self._search_duckduckgo()

        items = []
        for r in raw:
            title = self.clean_text(r.get("title"))
            url = r.get("url")
            snippet = self.clean_text(r.get("snippet"))
            if not title or not url:
                continue
            country, zone = self.guess_country_zone(f"{title} {snippet}", self.default_zone)
            items.append(TenderItem(
                title=title,
                url=url,
                source_id=self.source_id,
                source_name=self.source_name,
                zone=zone,
                entity="LinkedIn",
                category=self.guess_category(f"{title} {snippet}"),
                country=country,
                description=snippet,
                dedupe_key=f"linkedin|{url}",
            ))
        return items

    # --- Providers ---

    def _search_serper(self, num: int = 20):
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": SEARCH_QUERY, "num": num},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet")}
            for item in data.get("organic", [])
        ]

    def _search_serpapi(self, num: int = 20):
        resp = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": SEARCH_QUERY, "num": num, "api_key": SERPAPI_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet")}
            for item in data.get("organic_results", [])
        ]

    def _search_google_cse(self, num_pages: int = 2):
        """Google Programmable Search Engine (Custom Search JSON API).

        Solution officielle Google, gratuite jusqu'a 100 requetes/jour.
        L'API pagine par blocs de 10 resultats (parametre "start").
        """
        results = []
        for page in range(num_pages):
            start = 1 + page * 10
            try:
                resp = requests.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": GOOGLE_CSE_API_KEY,
                        "cx": GOOGLE_CSE_ID,
                        "q": SEARCH_QUERY,
                        "start": start,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
            except Exception:
                break
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                results.append({
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet"),
                })
        return results

    def _search_duckduckgo(self):
        """Fallback sans cle API. Moins fiable / quotas incertains a long terme."""
        try:
            resp = self.get("https://html.duckduckgo.com/html/", params={"q": SEARCH_QUERY})
        except Exception:
            return []
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            target = self._extract_ddg_target(href)
            if not target or "linkedin.com" not in target:
                continue
            snippet_el = a.find_parent(class_="result") or a.find_parent()
            snippet = None
            if snippet_el:
                snippet_tag = snippet_el.find(class_="result__snippet")
                snippet = self.clean_text(snippet_tag.get_text()) if snippet_tag else None
            results.append({"title": self.clean_text(a.get_text()), "url": target, "snippet": snippet})
        return results

    @staticmethod
    def _extract_ddg_target(href: str) -> str:
        if href.startswith("//duckduckgo.com/l/"):
            href = "https:" + href
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
        return href if href.startswith("http") else ""
