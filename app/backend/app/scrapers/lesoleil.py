"""
Scraper Le Soleil (lesoleil.sn) - quotidien national du Senegal.

Le site est un WordPress qui expose les avis via l'API REST officielle :
  - /wp-json/wp/v2/marche-public   : appels d'offres / marches publics
  - /wp-json/wp/v2/annonce-legale  : annonces legales (souvent des AMI/avis)

Les titres des posts sont generiques ("Appel d'Offres"), le vrai contenu
(autorite contractante + objet) est dans le corps HTML : on en extrait un
titre lisible.
"""
from __future__ import annotations

import re

from .base import BaseScraper, TenderItem

API_MARCHES = "https://lesoleil.sn/wp-json/wp/v2/marche-public?per_page=50&orderby=date&order=desc"
API_ANNONCES = "https://lesoleil.sn/wp-json/wp/v2/annonce-legale?per_page=20&orderby=date&order=desc"

TAG_RE = re.compile(r"<[^>]+>")


class LeSoleilScraper(BaseScraper):
    source_id = "lesoleil"
    source_name = "Le Soleil"
    source_url = "https://lesoleil.sn/"
    default_zone = "senegal"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        for api_url, is_marche in ((API_MARCHES, True), (API_ANNONCES, False)):
            try:
                posts = self.get(api_url).json()
            except Exception:
                continue
            for post in posts:
                item = self._post_to_item(post, is_marche)
                if item:
                    items.append(item)
        return items

    def _post_to_item(self, post: dict, is_marche: bool) -> TenderItem | None:
        link = post.get("link")
        if not link:
            return None
        raw_title = self.clean_text(TAG_RE.sub(" ", post.get("title", {}).get("rendered", ""))) or ""
        content = self.clean_text(TAG_RE.sub(" ", post.get("content", {}).get("rendered", ""))) or ""
        content = content.replace("&rsquo;", "'").replace("&nbsp;", " ").replace("&amp;", "&")

        # Titre generique ("Appel d'Offres") -> on construit un titre parlant
        # a partir du debut du contenu (autorite + objet).
        title = raw_title
        if len(title) < 30 and content:
            title = f"{raw_title} - {content[:140]}".strip(" -")
        if not title:
            return None

        category = self.guess_category(f"{raw_title} {content[:300]}")
        if category == "autre" and is_marche:
            category = "appel_offre"

        return TenderItem(
            title=title,
            url=link,
            source_id=self.source_id,
            source_name=self.source_name,
            zone=self.default_zone,
            category=category,
            country="Senegal",
            published_date=(post.get("date") or "")[:10] or None,
            description=content[:400] or None,
            dedupe_key=f"lesoleil|{post.get('id') or link}",
        )
