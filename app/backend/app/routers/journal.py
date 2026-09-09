"""
Depot quotidien des journaux papier par l'assistante.

Chaque jour ouvre, l'assistante doit soit joindre les photos des avis parus
dans la presse papier, soit declarer NEANT / RAS. L'absence de depot est
visible par l'administrateur (voir routers/admin.py).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from .. import auth, storage
from ..config import ALLOWED_PHOTO_EXTENSIONS
from ..database import get_db
from ..models import JournalEntry, JournalPhoto, Selection, User
from ..workflow_schemas import (
    JournalComplianceOut,
    JournalEntryOut,
    JournalStatusIn,
)
from ..workflow_service import build_journal_compliance, serialize_photo

router = APIRouter(prefix="/api/journal", tags=["journaux papier"])

VALID_DECLARATIONS = {"neant", "ras"}


def _parse_entry_date(value: Optional[str]) -> str:
    """Valide une date de depot : format ISO, jamais dans le futur."""
    if not value:
        return date.today().isoformat()
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="Date invalide (format attendu : AAAA-MM-JJ).")
    if parsed > date.today():
        raise HTTPException(status_code=400, detail="Impossible de déposer les journaux d'une date future.")
    return parsed.isoformat()


def _serialize_entry(db: Session, entry: JournalEntry) -> JournalEntryOut:
    photo_ids = [p.id for p in entry.photos]
    selections_by_photo = {}
    if photo_ids:
        rows = db.query(Selection).filter(Selection.journal_photo_id.in_(photo_ids)).all()
        selections_by_photo = {s.journal_photo_id: s for s in rows}

    return JournalEntryOut(
        id=entry.id,
        entry_date=entry.entry_date,
        status=entry.status,
        note=entry.note,
        user_id=entry.user_id,
        user_name=(entry.user.full_name or entry.user.username) if entry.user else None,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        photos=[serialize_photo(p, selections_by_photo.get(p.id)) for p in entry.photos],
    )


def _get_or_create_entry(db: Session, user: User, entry_date: str, status: str) -> JournalEntry:
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.entry_date == entry_date, JournalEntry.user_id == user.id)
        .first()
    )
    if entry is None:
        entry = JournalEntry(entry_date=entry_date, user_id=user.id, status=status)
        db.add(entry)
        db.flush()
    return entry


@router.get("/entries", response_model=list[JournalEntryOut])
def list_entries(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    user_id: Optional[int] = None,
    limit: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    """Historique des depots. Tous les profils connectes peuvent le consulter :
    le responsable selection a besoin de voir les avis parus dans la presse."""
    query = db.query(JournalEntry)
    if from_date:
        query = query.filter(JournalEntry.entry_date >= _parse_entry_date(from_date))
    if to_date:
        query = query.filter(JournalEntry.entry_date <= _parse_entry_date(to_date))
    if user_id:
        query = query.filter(JournalEntry.user_id == user_id)

    entries = query.order_by(JournalEntry.entry_date.desc()).limit(limit).all()
    return [_serialize_entry(db, e) for e in entries]


@router.get("/today", response_model=Optional[JournalEntryOut])
def today_entry(
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    """Depot du jour de l'utilisateur connecte (null s'il n'a pas encore depose)."""
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.entry_date == date.today().isoformat(), JournalEntry.user_id == current.id)
        .first()
    )
    return _serialize_entry(db, entry) if entry else None


@router.post("/photos", response_model=JournalEntryOut)
def upload_photos(
    files: list[UploadFile] = File(..., description="Photos ou scans des avis parus dans la presse"),
    entry_date: Optional[str] = Form(None),
    newspaper: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles("assistante")),
):
    """Joint une ou plusieurs photos de journaux papier a la journee indiquee."""
    day = _parse_entry_date(entry_date)
    entry = _get_or_create_entry(db, current, day, "photos")

    # Une journee declaree NEANT/RAS qui recoit finalement une photo repasse en
    # statut "photos" : c'est bien qu'un avis a ete trouve.
    entry.status = "photos"

    saved = []
    for upload in files:
        meta = storage.save_upload(upload, f"journaux/{day}", ALLOWED_PHOTO_EXTENSIONS)
        photo = JournalPhoto(
            entry_id=entry.id,
            stored_path=meta["stored_path"],
            original_name=meta["original_name"],
            content_type=meta["content_type"],
            size_bytes=meta["size_bytes"],
            newspaper=newspaper,
            caption=caption,
        )
        db.add(photo)
        saved.append(meta["original_name"])

    auth.log_activity(
        db, current, "depot_journaux",
        target_type="journal_entry", target_id=entry.id,
        detail=f"{day} : {len(saved)} fichier(s) joint(s) ({', '.join(saved)})",
    )
    db.commit()
    db.refresh(entry)
    return _serialize_entry(db, entry)


@router.post("/status", response_model=JournalEntryOut)
def declare_status(
    payload: JournalStatusIn,
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles("assistante")),
):
    """Declare NEANT (aucun appel d'offres paru) ou RAS pour la journee."""
    status = (payload.status or "").strip().lower()
    if status not in VALID_DECLARATIONS:
        raise HTTPException(status_code=400, detail="Statut attendu : 'neant' ou 'ras'.")

    day = _parse_entry_date(payload.entry_date)
    entry = _get_or_create_entry(db, current, day, status)

    if entry.photos:
        raise HTTPException(
            status_code=400,
            detail="Des photos ont déjà été jointes pour cette journée : "
                   "supprimez-les avant de déclarer NÉANT ou RAS.",
        )

    entry.status = status
    entry.note = payload.note

    auth.log_activity(
        db, current, "declaration_journaux",
        target_type="journal_entry", target_id=entry.id,
        detail=f"{day} : {status.upper()}" + (f" - {payload.note}" if payload.note else ""),
    )
    db.commit()
    db.refresh(entry)
    return _serialize_entry(db, entry)


@router.delete("/photos/{photo_id}")
def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles("assistante")),
):
    photo = db.query(JournalPhoto).filter(JournalPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo introuvable.")

    entry = photo.entry
    if entry.user_id != current.id and current.role != "admin":
        raise HTTPException(status_code=403, detail="Cette photo a été déposée par un autre compte.")

    linked = db.query(Selection).filter(Selection.journal_photo_id == photo.id).first()
    if linked:
        raise HTTPException(
            status_code=400,
            detail="Cet avis a déjà fait l'objet d'une décision de soumission : "
                   "la photo ne peut plus être supprimée.",
        )

    stored_path = photo.stored_path
    db.delete(photo)
    db.flush()

    # Si c'etait la derniere photo, la journee redevient un depot sans piece :
    # on la conserve en base pour ne pas la faire apparaitre comme manquante,
    # mais l'assistante doit alors declarer NEANT ou RAS.
    auth.log_activity(
        db, current, "suppression_photo_journal",
        target_type="journal_entry", target_id=entry.id,
        detail=f"{entry.entry_date} : {photo.original_name}",
    )
    db.commit()
    storage.delete_file(stored_path)

    db.refresh(entry)
    return _serialize_entry(db, entry)


@router.get("/compliance", response_model=JournalComplianceOut)
def compliance(
    days: int = Query(30, ge=1, le=365),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    """Historique de conformite : jours faits, jours manquants, taux de suivi.

    Une assistante ne voit que son propre historique ; l'administrateur voit
    celui de tout le monde (ou d'un compte precis via user_id).
    """
    if current.role == "assistante":
        user_id = current.id
    return build_journal_compliance(db, days=days, user_id=user_id)
