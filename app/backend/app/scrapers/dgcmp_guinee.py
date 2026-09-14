"""
Scraper DGCMP Guinee (Direction Generale du Controle des Marches Publics).

L'ancienne adresse www.dgcmp.mef.gov.gn affiche "Site en construction" : la
DGCMP publie desormais sur dgcmp.gov.gn, un WordPress dont l'API REST est
ouverte. On lit directement les articles des categories d'avis ouvertes
(AAO ouvert / international / restreint, AMI). Les categories "attribution
des marches" et "plan de passation" sont ignorees : ce ne sont pas des
opportunites. Le detail de l'avis est le plus souvent un PDF joint a l'article,
la date limite n'est donc generalement pas connue.

Le serveur coupe regulierement les connexions : chaque appel est retente.
"""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone

from .base import BaseScraper, TenderItem

API_URL = "https://dgcmp.gov.gn/wp-json/wp/v2/posts"
# id WordPress -> libelle (voir /wp-json/wp/v2/categories)
OPPORTUNITY_CATEGORIES = {
    1: "Avis d'appel d'offres ouvert",
    83: "Avis d'appels d'offres",
    126: "Appel a manifestation d'interet",
    127: "Appels d'offres restreint",
    128: "Appels d'offres international",
}
PER_PAGE = 50
PAGES_TO_FETCH = 2
MAX_AGE_DAYS = 90
TAG_RE = re.compile(r"<[^>]+>")


class DgcmpGuineeScraper(BaseScraper):
    source_id = "dgcmp_guinee"
    source_name = "DGCMP Guinee Conakry"
    source_url = "https://dgcmp.gov.gn/appels-doffres/"
    default_zone = "uemoa"

    def fetch(self) -> list[TenderItem]:
        items: list[TenderItem] = []
        for page in range(1, PAGES_TO_FETCH + 1):
            resp = self._get_with_retry(API_URL, params={
                "categories": ",".join(str(c) for c in OPPORTUNITY_CATEGORIES),
                # Date limite rarement connue : sans cette borne, de vieux avis
                # resteraient affiches "en cours" indefiniment.
                "after": (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).strftime("%Y-%m-%dT00:00:00"),
                "per_page": PER_PAGE,
                "page": page,
                "orderby": "date",
                "order": "desc",
                "_fields": "id,date,link,title,categories,excerpt",
            })
            posts = resp.json()
            for post in posts:
                item = self._to_item(post)
                if item:
                    items.append(item)
            total_pages = int(resp.headers.get("X-WP-TotalPages") or 1)
            if len(posts) < PER_PAGE or page >= total_pages:
                break
        return items

    def _get_with_retry(self, url: str, params: dict, attempts: int = 3):
        for attempt in range(attempts):
            try:
                return self.get(url, params=params, timeout=45)
            except Exception:
                if attempt == attempts - 1:
                    raise
                time.sleep(3)

    def _to_item(self, post: dict) -> TenderItem | None:
        title = self._text((post.get("title") or {}).get("rendered"))
        link = post.get("link")
        if not title or not link:
            return None
        excerpt = self._text((post.get("excerpt") or {}).get("rendered"))
        categories = [OPPORTUNITY_CATEGORIES[c] for c in post.get("categories", []) if c in OPPORTUNITY_CATEGORIES]
        category = self.guess_category(f"{title} {' '.join(categories)}")
        if category == "autre":
            category = "ami" if 126 in post.get("categories", []) else "appel_offre"

        return TenderItem(
            title=title[:300],
            url=link,
            source_id=self.source_id,
            source_name=self.source_name,
            zone="uemoa",
            entity="DGCMP Guinee",
            category=category,
            country="Guinee",
            published_date=(post.get("date") or "")[:10] or None,
            description=self.clean_text(" - ".join(filter(None, [", ".join(categories), excerpt]))),
            dedupe_key=f"dgcmp_guinee|{post.get('id') or link}",
        )

    def _text(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.clean_text(html.unescape(TAG_RE.sub(" ", value)))
