"""
Regles metier de l'espace de travail interne.

Trois responsabilites :
  1. Mettre en forme une selection (avis retenu) avec son etat de dossier.
  2. Calculer l'historique de conformite du depot quotidien des journaux.
  3. Construire la liste des alertes destinees a l'administrateur.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import config
from .models import JournalEntry, Selection, SubmissionDocument, User
from .workflow_schemas import (
    AlertOut,
    JournalComplianceOut,
    JournalDayOut,
    JournalPhotoOut,
    SelectionOut,
    SubmissionDocumentOut,
)

REQUIRED_DOC_TYPES = ["technique", "financiere"]
DOC_LABELS = {"technique": "Offre technique", "financiere": "Offre financière"}

WEEKDAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _parse_iso(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Selections / dossiers
# --------------------------------------------------------------------------
def serialize_document(doc: SubmissionDocument) -> SubmissionDocumentOut:
    return SubmissionDocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        original_name=doc.original_name,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        uploaded_at=doc.uploaded_at,
        uploaded_by_name=(doc.uploaded_by.full_name or doc.uploaded_by.username) if doc.uploaded_by else None,
        file_url=f"/api/files/document/{doc.id}",
    )


def serialize_photo(photo, selection: Optional[Selection] = None) -> JournalPhotoOut:
    return JournalPhotoOut(
        id=photo.id,
        original_name=photo.original_name,
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        newspaper=photo.newspaper,
        caption=photo.caption,
        uploaded_at=photo.uploaded_at,
        file_url=f"/api/files/journal/{photo.id}",
        selection_id=selection.id if selection else None,
        selection_decision=selection.decision if selection else None,
    )


def dossier_status(selection: Selection, today: Optional[date] = None) -> tuple[str, Optional[int], list[str]]:
    """Etat d'avancement du dossier : (statut, jours restants, pieces manquantes).

    Statuts possibles :
      - rejete      : l'avis n'a pas ete retenu, aucun dossier attendu
      - complet     : offres technique ET financiere deposees
      - en_retard   : date limite passee et dossier incomplet
      - urgent      : date limite proche (voir DOC_ALERT_DAYS_BEFORE_DEADLINE)
      - en_cours    : dossier incomplet mais l'echeance laisse du temps
    """
    today = today or date.today()
    present = {doc.doc_type for doc in selection.documents}
    missing = [t for t in REQUIRED_DOC_TYPES if t not in present]

    deadline = _parse_iso(selection.deadline_iso)
    days_left = (deadline - today).days if deadline else None

    if selection.decision != "retenu":
        return "rejete", days_left, missing
    if not missing:
        return "complet", days_left, missing
    if days_left is not None and days_left < 0:
        return "en_retard", days_left, missing
    if days_left is not None and days_left <= config.DOC_ALERT_DAYS_BEFORE_DEADLINE:
        return "urgent", days_left, missing
    return "en_cours", days_left, missing


def serialize_selection(selection: Selection, today: Optional[date] = None) -> SelectionOut:
    status, days_left, missing = dossier_status(selection, today)
    present = {doc.doc_type for doc in selection.documents}
    return SelectionOut(
        id=selection.id,
        tender_id=selection.tender_id,
        journal_photo_id=selection.journal_photo_id,
        title=selection.title,
        entity=selection.entity,
        category=selection.category,
        deadline_iso=selection.deadline_iso,
        url=selection.url,
        decision=selection.decision,
        comment=selection.comment,
        selected_by_id=selection.selected_by_id,
        selected_by_name=(
            (selection.selected_by.full_name or selection.selected_by.username)
            if selection.selected_by else None
        ),
        assigned_to_id=selection.assigned_to_id,
        assigned_to_name=(
            (selection.assigned_to.full_name or selection.assigned_to.username)
            if selection.assigned_to else None
        ),
        is_complete=selection.is_complete,
        submitted_at=selection.submitted_at,
        created_at=selection.created_at,
        documents=[serialize_document(d) for d in selection.documents],
        has_technique="technique" in present,
        has_financiere="financiere" in present,
        missing_documents=[DOC_LABELS[t] for t in missing],
        days_left=days_left,
        dossier_status=status,
    )


def refresh_completion(selection: Selection) -> None:
    """Met a jour is_complete/submitted_at apres ajout ou retrait d'une piece."""
    from datetime import datetime, timezone

    present = {doc.doc_type for doc in selection.documents}
    complete = all(t in present for t in REQUIRED_DOC_TYPES)
    selection.is_complete = complete
    if complete and selection.submitted_at is None:
        selection.submitted_at = datetime.now(timezone.utc)
    elif not complete:
        selection.submitted_at = None


# --------------------------------------------------------------------------
# Conformite du depot quotidien des journaux
# --------------------------------------------------------------------------
def is_working_day(day: date) -> bool:
    return day.weekday() in config.JOURNAL_WORKING_DAYS


def build_journal_compliance(
    db: Session,
    *,
    days: int = 30,
    user_id: Optional[int] = None,
    today: Optional[date] = None,
) -> JournalComplianceOut:
    """Historique jour par jour des depots de journaux sur la periode demandee.

    Sans user_id, une journee est consideree faite des qu'un depot existe, quel
    que soit son auteur (utile quand plusieurs assistantes se relaient).
    """
    today = today or date.today()
    start = today - timedelta(days=days - 1)

    query = db.query(JournalEntry).filter(
        JournalEntry.entry_date >= start.isoformat(),
        JournalEntry.entry_date <= today.isoformat(),
    )
    if user_id is not None:
        query = query.filter(JournalEntry.user_id == user_id)

    entries_by_date: dict[str, JournalEntry] = {}
    for entry in query.order_by(JournalEntry.entry_date).all():
        entries_by_date[entry.entry_date] = entry

    days_out: list[JournalDayOut] = []
    working = done = missing = 0

    for offset in range(days):
        current = start + timedelta(days=offset)
        iso = current.isoformat()
        entry = entries_by_date.get(iso)
        working_day = is_working_day(current)

        if working_day:
            working += 1

        if entry:
            done += 1
            days_out.append(JournalDayOut(
                date=iso,
                weekday=WEEKDAY_LABELS[current.weekday()],
                is_working_day=working_day,
                done=True,
                status=entry.status,
                photo_count=len(entry.photos),
                user_name=(entry.user.full_name or entry.user.username) if entry.user else None,
                entry_id=entry.id,
                submitted_at=entry.created_at,
                is_missing=False,
            ))
        else:
            # Le jour en cours n'est pas encore "manquant" : la journee n'est
            # pas finie, l'assistante peut encore deposer.
            is_missing = working_day and current < today
            if is_missing:
                missing += 1
            days_out.append(JournalDayOut(
                date=iso,
                weekday=WEEKDAY_LABELS[current.weekday()],
                is_working_day=working_day,
                done=False,
                photo_count=0,
                is_missing=is_missing,
            ))

    expected = max(working - (1 if is_working_day(today) else 0), 0)
    rate = round(100.0 * (expected - missing) / expected, 1) if expected else 100.0

    target_user = db.query(User).filter(User.id == user_id).first() if user_id else None

    return JournalComplianceOut(
        user_id=user_id,
        user_name=(target_user.full_name or target_user.username) if target_user else None,
        from_date=start.isoformat(),
        to_date=today.isoformat(),
        working_days=working,
        days_done=done,
        days_missing=missing,
        completion_rate=rate,
        today_done=today.isoformat() in entries_by_date,
        days=list(reversed(days_out)),
    )


# --------------------------------------------------------------------------
# Alertes administrateur
# --------------------------------------------------------------------------
def build_alerts(db: Session, *, days: int = 30, today: Optional[date] = None) -> list[AlertOut]:
    """Ce que l'administrateur doit voir : depots de journaux manquants et
    dossiers dont les offres ne sont pas jointes a l'approche de l'echeance."""
    today = today or date.today()
    alerts: list[AlertOut] = []

    compliance = build_journal_compliance(db, days=days, today=today)
    for day in compliance.days:
        if day.is_missing:
            missing_day = date.fromisoformat(day.date)
            alerts.append(AlertOut(
                kind="journal_manquant",
                severity="critique" if (today - missing_day).days <= 3 else "info",
                title=f"Journaux non déposés — {day.weekday} {missing_day.strftime('%d/%m/%Y')}",
                detail="Aucune photo et aucune déclaration NÉANT / RAS pour cette journée ouvrée.",
                date=day.date,
            ))

    selections = (
        db.query(Selection)
        .filter(Selection.decision == "retenu", Selection.is_complete.is_(False))
        .all()
    )
    for selection in selections:
        status, days_left, missing = dossier_status(selection, today)
        if status not in ("en_retard", "urgent"):
            continue
        responsable = (
            (selection.assigned_to.full_name or selection.assigned_to.username)
            if selection.assigned_to else "non assigné"
        )
        if status == "en_retard":
            detail = (
                f"Date limite dépassée depuis {abs(days_left)} jour(s). "
                f"Pièce(s) jamais jointe(s) : {', '.join(DOC_LABELS[m] for m in missing)}. "
                f"Responsable : {responsable}."
            )
        else:
            detail = (
                f"Échéance dans {days_left} jour(s). "
                f"Pièce(s) manquante(s) : {', '.join(DOC_LABELS[m] for m in missing)}. "
                f"Responsable : {responsable}."
            )
        alerts.append(AlertOut(
            kind="dossier_incomplet",
            severity="critique" if status == "en_retard" else "urgent",
            title=selection.title[:180],
            detail=detail,
            date=selection.deadline_iso,
            target_id=selection.id,
            days_left=days_left,
        ))

    severity_order = {"critique": 0, "urgent": 1, "info": 2}
    alerts.sort(key=lambda a: (severity_order.get(a.severity, 3), a.date or ""))
    return alerts
