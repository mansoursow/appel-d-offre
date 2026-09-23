"""
Historique des prix : ce que le cabinet et ses concurrents ont propose.

Sert a preparer une offre : avant de chiffrer un marche du meme type, on
regarde ce qu'ADOC avait propose, qui l'a emporte et a quel prix, et ce que
chaque concurrent pratique d'habitude.

Consultation ouverte a tous les profils connectes ; seul l'administrateur peut
remplacer l'historique en envoyant une nouvelle version du classeur.
"""
from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from .. import auth, config, price_service
from ..database import get_db
from ..models import User
from ..workflow_schemas import PriceHistoryOut

router = APIRouter(prefix="/api/prix", tags=["historique des prix"])

MAX_WORKBOOK_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024


@router.get("", response_model=PriceHistoryOut)
def price_history(
    search: Optional[str] = Query(None, description="Objet, structure ou nom d'un concurrent"),
    annee: Optional[int] = Query(None),
    methode: Optional[str] = Query(None),
    nature: Optional[str] = Query(None, description="Code de nature (cac, psd, audit_projet...)"),
    issue: Optional[str] = Query(None, pattern="^(gagnes|perdus)$"),
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    return price_service.build_price_history(
        db, search=search, annee=annee, methode=methode, nature=nature, issue=issue
    )


@router.post("/import", response_model=PriceHistoryOut)
async def import_workbook(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(auth.require_roles(*config.ADMIN_ROLES)),
):
    """Remplace l'historique par le contenu du classeur des MI et PTF."""
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Envoyez le classeur Excel (.xlsx).")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Fichier vide.")
    if len(raw) > MAX_WORKBOOK_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Classeur trop volumineux (maximum {config.MAX_UPLOAD_MB} Mo).",
        )

    try:
        count = price_service.replace_from_workbook(db, io.BytesIO(raw))
    except Exception as exc:  # classeur illisible ou structure inattendue
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Classeur illisible : {exc}",
        ) from exc

    if not count:
        raise HTTPException(
            status_code=400,
            detail="Aucun marche chiffre trouve. Verifiez la colonne "
                   "« Prix des participants (TTC) » du classeur.",
        )

    auth.log_activity(
        db, user, "import_prix",
        detail=f"{count} marche(s) chiffre(s) importe(s) depuis {file.filename}",
    )
    db.commit()
    return price_service.build_price_history(db)
