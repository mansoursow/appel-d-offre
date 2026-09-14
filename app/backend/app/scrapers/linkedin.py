"""
Module LinkedIn "via Google" (Google dorking), comme demande par l'utilisateur :

    site:linkedin.com/posts "appel d'offres" (Senegal OR "Cote d'Ivoire" ...)

Plutot que de scraper LinkedIn directement (bloque tres vite) ou de scraper
directement google.com/search (bloque tres vite aussi : CAPTCHA, IP ban), on
interroge un moteur de recherche via une API, et on recupere les URLs de posts
LinkedIn pertinents + le snippet affiche.

Providers possibles, dans cet ordre de preference :
  1. Serper.dev            (SERPER_API_KEY)              - vrais resultats Google, credits gratuits a l'inscription puis payant
  2. SerpApi                (SERPAPI_API_KEY)             - vrais resultats Google, payant
  3. Google Programmable Search Engine / Custom Search API (GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID)
  4. DuckDuckGo HTML        (aucune cle)                  - en pratique BLOQUE : DuckDuckGo renvoie une page
                                                            anti-robot aux requetes automatiques

Sans cle, la collecte echoue avec un message explicite (visible dans
Administration > Sources de la veille) au lieu de renvoyer 0 resultat en silence.
La cle se renseigne en variable d'environnement (Railway : onglet Variables).
"""
from __future__ import annotations

from urllib.parse import unquote, urlparse, parse_qs

import requests

from ..config import (
    DEFAULT_HEADERS, REQUEST_TIMEOUT,
    SERPER_API_KEY, SERPAPI_API_KEY, GOOGLE_CSE_API_KEY, GOOGLE_CSE_ID,
)
from .base import BaseScraper, TenderItem

COUNTRIES_QUERY = ('(Sénégal OR Senegal OR "Côte d\'Ivoire" OR Mali OR "Burkina Faso" '
                   'OR Bénin OR Togo OR Niger OR Guinée)')
# Syntaxe Google : OR en majuscules, un espace vaut ET. Plusieurs requetes
# courtes ramenent plus de posts qu'une seule requete tres longue.
SEARCH_QUERIES = [
    f'site:linkedin.com/posts ("appel d\'offres" OR "avis d\'appel d\'offres") {COUNTRIES_QUERY}',
    f'site:linkedin.com/posts ("manifestation d\'intérêt" OR "termes de référence") {COUNTRIES_QUERY}',
    f'site:linkedin.com/posts ("recrutement d\'un cabinet" OR "recrutement d\'un consultant" OR audit) '
    f'("appel d\'offres" OR "manifestation d\'intérêt") {COUNTRIES_QUERY}',
]
# Serper / SerpApi : limiter aux publications du dernier mois.
RECENCY = "qdr:m"


class LinkedInGoogleScraper(BaseScraper):
    source_id = "linkedin"
    source_name = "LinkedIn (recherche Google)"
    source_url = "https://www.linkedin.com/"
    default_zone = "international"

    def fetch(self) -> list[TenderItem]:
        if SERPER_API_KEY:
            search = self._search_serper
        elif SERPAPI_API_KEY:
            search = self._search_serpapi
        elif GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID:
            search = self._search_google_cse
        else:
            search = self._search_duckduckgo

        items = []
        seen: set[str] = set()
        for query in SEARCH_QUERIES:
            for r in search(query):
                title = self.clean_text(r.get("title"))
                url = (r.get("url") or "").split("?")[0]
                snippet = self.clean_text(r.get("snippet"))
                if not title or "linkedin.com" not in url or url in seen:
                    continue
                seen.add(url)
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
                    # texte fourni par le moteur ("il y a 3 jours", "12 sept. 2026"...)
                    published_date=(r.get("date") or "")[:30] or None,
                    description=snippet,
                    dedupe_key=f"linkedin|{url}",
                ))
        return items

    # --- Providers ---

    def _search_serper(self, query: str, num: int = 20):
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num, "gl": "sn", "hl": "fr", "tbs": RECENCY},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (401, 403):
            raise RuntimeError("Clé SERPER_API_KEY refusée par Serper (clé invalide ou crédits épuisés).")
        resp.raise_for_status()
        return [
            {"title": item.get("title"), "url": item.get("link"),
             "snippet": item.get("snippet"), "date": item.get("date")}
            for item in resp.json().get("organic", [])
        ]

    def _search_serpapi(self, query: str, num: int = 20):
        resp = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "num": num, "tbs": RECENCY,
                    "hl": "fr", "api_key": SERPAPI_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (401, 403):
            raise RuntimeError("Clé SERPAPI_API_KEY refusée par SerpApi (clé invalide ou crédits épuisés).")
        resp.raise_for_status()
        return [
            {"title": item.get("title"), "url": item.get("link"),
             "snippet": item.get("snippet"), "date": item.get("date")}
            for item in resp.json().get("organic_results", [])
        ]

    def _search_google_cse(self, query: str):
        """Google Programmable Search Engine (Custom Search JSON API), 10 resultats."""
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": GOOGLE_CSE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "dateRestrict": "m1"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (400, 401, 403):
            raise RuntimeError(f"Google Custom Search a refusé la requête ({resp.status_code}) : "
                               "vérifier GOOGLE_CSE_API_KEY / GOOGLE_CSE_ID.")
        resp.raise_for_status()
        return [
            {"title": item.get("title"), "url": item.get("link"), "snippet": item.get("snippet")}
            for item in resp.json().get("items", [])
        ]

    def _search_duckduckgo(self, query: str):
        """Fallback sans cle API : DuckDuckGo bloque presque toujours les robots."""
        blocked = RuntimeError(
            "Aucune clé de recherche configurée (SERPER_API_KEY conseillée) et DuckDuckGo "
            "bloque les requêtes automatiques : impossible de chercher les posts LinkedIn."
        )
        try:
            resp = self.get("https://html.duckduckgo.com/html/", params={"q": query})
        except Exception:
            raise blocked
        if resp.status_code == 202 or "anomaly" in resp.text.lower():
            raise blocked
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result__a"):
            target = self._extract_ddg_target(a.get("href", ""))
            if not target:
                continue
            snippet_el = a.find_parent(class_="result") or a.find_parent()
            snippet_tag = snippet_el.find(class_="result__snippet") if snippet_el else None
            results.append({
                "title": self.clean_text(a.get_text()),
                "url": target,
                "snippet": self.clean_text(snippet_tag.get_text()) if snippet_tag else None,
            })
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
