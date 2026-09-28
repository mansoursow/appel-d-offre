"""
Relais local : reception des avis collectes depuis le Senegal.

Le portail officiel www.marchespublics.sn n'accepte que les connexions venant
du Senegal (verifie depuis 12 pays : connexion refusee partout). L'application
etant hebergee en Europe, elle ne peut pas l'interroger elle-meme.

Un petit programme tourne donc sur un poste a Dakar (voir collect_local.py),
interroge le site et depose ici les avis trouves. Le depot est protege par un
jeton partage (variable d'environnement INGEST_TOKEN) : sans jeton configure,
la route est fermee.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import config, scraper_service
from ..config import SOURCE_BY_ID
from ..database import get_db
from ..scrapers.base import TenderItem
from ..schemas import IngestIn, RefreshResultOut

router = APIRouter(prefix="/api/ingest", tags=["relais local"])


def _check_token(token: str | None) -> None:
    if not config.INGEST_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Le relais local n'est pas configuré sur le serveur (INGEST_TOKEN manquant).",
        )
    if not token or not secrets.compare_digest(token, config.INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="Jeton de relais invalide.")


@router.post("/{source_id}", response_model=RefreshResultOut)
def ingest(
    source_id: str,
    payload: IngestIn,
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    db: Session = Depends(get_db),
):
    """Enregistre les avis envoyes par le relais local, comme le ferait une
    collecte faite sur le serveur (meme dedoublonnage, meme suivi)."""
    _check_token(x_ingest_token)

    meta = SOURCE_BY_ID.get(source_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Source inconnue.")
    if meta.get("status") != "relais_local":
        raise HTTPException(
            status_code=400,
            detail="Cette source est collectée par le serveur : le relais local n'a pas à l'envoyer.",
        )

    items = [
        TenderItem(
            title=item.title,
            url=item.url,
            source_id=source_id,
            source_name=meta["name"],
            zone=item.zone or meta["zone"],
            entity=item.entity,
            category=item.category,
            country=item.country,
            published_date=item.published_date,
            deadline_date=item.deadline_date,
            description=item.description,
            dedupe_key=item.dedupe_key or "",
        )
        for item in payload.items
    ]

    result = scraper_service.save_items(db, source_id, meta["name"], items)
    scraper_service.record_run(db, result)
    return result
