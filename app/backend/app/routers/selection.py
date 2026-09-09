"""
Choix des avis a soumissionner, puis depot des offres technique et financiere.

Deux profils interviennent :
  - selectionneur : decide "retenu" / "rejete" sur un avis (issu de la veille
    automatique ou d'une photo de journal papier) et designe le responsable du
    montage du dossier ;
  - monteur : joint l'offre technique et l'offre financiere avant la date
    limite. Tant que les deux pieces manquent, le dossier remonte dans les
    alertes de l'administrateur.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from .. import auth, config, storage
from ..config import ALLOWED_DOC_EXTENSIONS, ROLE_LABELS
from ..database import get_db
from ..models import JournalPhoto, Selection, SubmissionDocument, Tender, User
from ..workflow_schemas import SelectionCreateIn, SelectionOut, SelectionUpdateIn, UserOut
from ..workflow_service import (
    DOC_LABELS,
    REQUIRED_DOC_TYPES,
    dossier_status,
    refresh_completion,
    serialize_selection,
)

router = APIRouter(prefix="/api", tags=["selection et dossiers"])


def _get_selection(db: Session, selection_id: int) -> Selection:
    selection = db.query(Selection).filter(Selection.id == selection_id).first()
    if not selection:
        raise HTTPException(status_code=404, detail="Décision introuvable.")
    return selection


@router.get("/users/assignable", response_model=list[UserOut])
def assignable_users(
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles(*config.ROLES_CAN_SELECT)),
):
    """Comptes pouvant recevoir le montage d'un dossier (profil "monteur").

    Le responsable selection en a besoin pour designer qui joindra les offres ;
    il n'a pas pour autant acces a la gestion complete des comptes.
    """
    users = (
        db.query(User)
        .filter(User.role == "monteur", User.is_active.is_(True))
        .order_by(User.username)
        .all()
    )
    return [
        UserOut(
            id=u.id,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            role_label=ROLE_LABELS.get(u.role, u.role),
            is_active=u.is_active,
            must_change_password=u.must_change_password,
        )
        for u in users
    ]


@router.get("/selections", response_model=list[SelectionOut])
def list_selections(
    decision: Optional[str] = Query(None, description="retenu | rejete"),
    status: Optional[str] = Query(None, description="complet | en_retard | urgent | en_cours"),
    assigned_to_me: bool = False,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    query = db.query(Selection)
    if decision:
        query = query.filter(Selection.decision == decision)
    if assigned_to_me:
        query = query.filter(Selection.assigned_to_id == current.id)

    items = [serialize_selection(s) for s in query.order_by(Selection.created_at.desc()).all()]
    if status:
        items = [i for i in items if i.dossier_status == status]
    return items


@router.get("/selections/{selection_id}", response_model=SelectionOut)
def get_selection(
    selection_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    return serialize_selection(_get_selection(db, selection_id))


@router.post("/selections", response_model=SelectionOut)
def create_selection(
    payload: SelectionCreateIn,
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles(*config.ROLES_CAN_SELECT)),
):
    """Enregistre la decision de soumissionner (ou non) sur un avis."""
    decision = (payload.decision or "retenu").strip().lower()
    if decision not in ("retenu", "rejete"):
        raise HTTPException(status_code=400, detail="Décision attendue : 'retenu' ou 'rejete'.")
    if not payload.tender_id and not payload.journal_photo_id:
        raise HTTPException(
            status_code=400,
            detail="Indiquez l'avis concerné (tender_id pour la veille, journal_photo_id pour la presse papier).",
        )

    title = payload.title
    entity = payload.entity
    category = payload.category
    deadline_iso = payload.deadline_iso
    url = payload.url

    if payload.tender_id:
        existing = db.query(Selection).filter(Selection.tender_id == payload.tender_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Une décision existe déjà pour cet avis.")
        tender = db.query(Tender).filter(Tender.id == payload.tender_id).first()
        if not tender:
            raise HTTPException(status_code=404, detail="Avis introuvable.")
        # On recopie la fiche : l'annonce peut disparaitre du site source, le
        # dossier interne doit rester lisible et exploitable.
        title = title or tender.title
        entity = entity or tender.entity
        category = category or tender.category
        deadline_iso = deadline_iso or tender.deadline_iso
        url = url or tender.url

    if payload.journal_photo_id:
        existing = db.query(Selection).filter(
            Selection.journal_photo_id == payload.journal_photo_id
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Une décision existe déjà pour cet avis papier.")
        photo = db.query(JournalPhoto).filter(JournalPhoto.id == payload.journal_photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail="Photo de journal introuvable.")
        title = title or photo.caption or f"Avis presse - {photo.newspaper or photo.original_name}"
        entity = entity or photo.newspaper

    if not title:
        raise HTTPException(status_code=400, detail="Un intitulé est nécessaire pour enregistrer la décision.")

    if payload.assigned_to_id:
        assignee = db.query(User).filter(User.id == payload.assigned_to_id).first()
        if not assignee or not assignee.is_active:
            raise HTTPException(status_code=400, detail="Le responsable désigné est introuvable ou désactivé.")

    selection = Selection(
        tender_id=payload.tender_id,
        journal_photo_id=payload.journal_photo_id,
        title=title,
        entity=entity,
        category=category,
        deadline_iso=deadline_iso,
        url=url,
        decision=decision,
        comment=payload.comment,
        selected_by_id=current.id,
        assigned_to_id=payload.assigned_to_id,
    )
    db.add(selection)
    db.flush()

    auth.log_activity(
        db, current, f"avis_{decision}",
        target_type="selection", target_id=selection.id,
        detail=f"{title[:150]}" + (f" | echeance {deadline_iso}" if deadline_iso else " | echeance inconnue"),
    )
    db.commit()
    db.refresh(selection)
    return serialize_selection(selection)


@router.patch("/selections/{selection_id}", response_model=SelectionOut)
def update_selection(
    selection_id: int,
    payload: SelectionUpdateIn,
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles(*config.ROLES_CAN_SELECT)),
):
    selection = _get_selection(db, selection_id)
    changes = []

    if payload.decision and payload.decision != selection.decision:
        if payload.decision not in ("retenu", "rejete"):
            raise HTTPException(status_code=400, detail="Décision attendue : 'retenu' ou 'rejete'.")
        changes.append(f"decision {selection.decision} -> {payload.decision}")
        selection.decision = payload.decision

    if payload.comment is not None:
        selection.comment = payload.comment

    if payload.deadline_iso is not None:
        try:
            date.fromisoformat(payload.deadline_iso[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="Date limite invalide (format attendu : AAAA-MM-JJ).")
        changes.append(f"echeance -> {payload.deadline_iso}")
        selection.deadline_iso = payload.deadline_iso

    if payload.assigned_to_id is not None:
        assignee = db.query(User).filter(User.id == payload.assigned_to_id).first()
        if not assignee or not assignee.is_active:
            raise HTTPException(status_code=400, detail="Le responsable désigné est introuvable ou désactivé.")
        changes.append(f"responsable -> {assignee.full_name or assignee.username}")
        selection.assigned_to_id = payload.assigned_to_id

    auth.log_activity(
        db, current, "modification_decision",
        target_type="selection", target_id=selection.id,
        detail="; ".join(changes) if changes else "commentaire mis a jour",
    )
    db.commit()
    db.refresh(selection)
    return serialize_selection(selection)


@router.post("/selections/{selection_id}/documents", response_model=SelectionOut)
def upload_document(
    selection_id: int,
    doc_type: str = Form(..., description="technique | financiere"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles("monteur")),
):
    """Joint l'offre technique ou financiere au dossier retenu."""
    doc_type = (doc_type or "").strip().lower()
    if doc_type not in REQUIRED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Type attendu : 'technique' ou 'financiere'.")

    selection = _get_selection(db, selection_id)
    if selection.decision != "retenu":
        raise HTTPException(
            status_code=400,
            detail="Cet avis n'a pas été retenu : aucun dossier n'est attendu.",
        )

    meta = storage.save_upload(file, f"dossiers/{selection.id}", ALLOWED_DOC_EXTENSIONS)

    # Un nouveau depot du meme type remplace le precedent (correction d'une
    # piece envoyee par erreur), l'ancien fichier est efface du disque.
    previous = (
        db.query(SubmissionDocument)
        .filter(SubmissionDocument.selection_id == selection.id, SubmissionDocument.doc_type == doc_type)
        .first()
    )
    replaced_path = None
    if previous:
        replaced_path = previous.stored_path
        db.delete(previous)
        db.flush()

    db.add(SubmissionDocument(
        selection_id=selection.id,
        doc_type=doc_type,
        stored_path=meta["stored_path"],
        original_name=meta["original_name"],
        content_type=meta["content_type"],
        size_bytes=meta["size_bytes"],
        uploaded_by_id=current.id,
    ))
    db.flush()
    db.refresh(selection)
    refresh_completion(selection)

    status, days_left, _ = dossier_status(selection)
    auth.log_activity(
        db, current, "depot_offre",
        target_type="selection", target_id=selection.id,
        detail=f"{DOC_LABELS[doc_type]} : {meta['original_name']}"
               + (f" (echeance dans {days_left} jour(s))" if days_left is not None else "")
               + (" [remplace le fichier precedent]" if replaced_path else ""),
    )
    db.commit()
    if replaced_path:
        storage.delete_file(replaced_path)

    db.refresh(selection)
    return serialize_selection(selection)


@router.delete("/documents/{document_id}", response_model=SelectionOut)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(auth.require_roles("monteur")),
):
    document = db.query(SubmissionDocument).filter(SubmissionDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Pièce introuvable.")

    selection = document.selection
    stored_path = document.stored_path
    label = DOC_LABELS.get(document.doc_type, document.doc_type)

    db.delete(document)
    db.flush()
    db.refresh(selection)
    refresh_completion(selection)

    auth.log_activity(
        db, current, "suppression_offre",
        target_type="selection", target_id=selection.id,
        detail=f"{label} retiree du dossier",
    )
    db.commit()
    storage.delete_file(stored_path)

    db.refresh(selection)
    return serialize_selection(selection)
