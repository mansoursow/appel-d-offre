"""
Acces aux fichiers deposes (photos de journaux, offres technique/financiere).

Les fichiers ne sont pas exposes en statique : chaque telechargement passe par
une route authentifiee, pour qu'un dossier de soumission ne soit pas lisible
par quiconque devine son URL.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import auth, storage
from ..database import get_db
from ..models import JournalPhoto, SubmissionDocument, User

router = APIRouter(prefix="/api/files", tags=["fichiers"])


@router.get("/journal/{photo_id}")
def get_journal_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    photo = db.query(JournalPhoto).filter(JournalPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable.")
    return FileResponse(
        storage.absolute_path(photo.stored_path),
        media_type=photo.content_type or "application/octet-stream",
        filename=photo.original_name,
        content_disposition_type="inline",
    )


@router.get("/document/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    document = db.query(SubmissionDocument).filter(SubmissionDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Pièce introuvable.")
    return FileResponse(
        storage.absolute_path(document.stored_path),
        media_type=document.content_type or "application/octet-stream",
        filename=document.original_name,
        content_disposition_type="inline",
    )
