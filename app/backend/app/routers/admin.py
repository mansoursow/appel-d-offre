"""
Supervision : alertes, journal d'activite et gestion des comptes.

Toutes les routes de ce module sont reservees a l'administrateur. C'est ici
qu'il constate :
  - les journees ou l'assistante n'a pas depose les journaux ;
  - qui a retenu ou rejete quel avis, et quand ;
  - les dossiers dont l'offre technique ou financiere n'est pas jointe alors
    que la date limite approche ou est deja passee.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from .. import auth, notifications
from ..config import ADMIN_ROLES, ROLE_LABELS, ROLES, SOURCES
from ..database import get_db
from ..models import ActivityLog, Selection, SourceRun, Tender, User
from ..scrapers.registry import ACTIVE_SCRAPERS_BY_ID
from ..workflow_schemas import (
    ActivityLogOut,
    AdminDashboardOut,
    AlertOut,
    JournalComplianceOut,
    SourceHealthOut,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from ..workflow_service import build_alerts, build_journal_compliance, dossier_status
from .auth_routes import user_out

router = APIRouter(prefix="/api/admin", tags=["administration"])

# Administrateur + profils ayant les memes droits (voir config.ADMIN_ROLES).
admin_only = auth.require_roles(*ADMIN_ROLES)


@router.get("/dashboard", response_model=AdminDashboardOut)
def dashboard(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    alerts = build_alerts(db, days=days)
    compliance = build_journal_compliance(db, days=days)

    retenues = db.query(Selection).filter(Selection.decision == "retenu").all()
    incomplets = 0
    en_retard = 0
    for selection in retenues:
        status, _, _ = dossier_status(selection)
        if status in ("en_cours", "urgent", "en_retard"):
            incomplets += 1
        if status == "en_retard":
            en_retard += 1

    return AdminDashboardOut(
        alerts=alerts,
        journal_missing_days=compliance.days_missing,
        journal_today_done=compliance.today_done,
        selections_retenues=len(retenues),
        dossiers_incomplets=incomplets,
        dossiers_en_retard=en_retard,
        users_count=db.query(User).filter(User.is_active.is_(True)).count(),
    )


@router.get("/alerts", response_model=list[AlertOut])
def alerts(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    return build_alerts(db, days=days)


@router.get("/journal-compliance", response_model=JournalComplianceOut)
def journal_compliance(
    days: int = Query(30, ge=1, le=365),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    """Historique jour par jour : depots faits, declarations NEANT/RAS,
    et journees ouvrees restees sans depot."""
    return build_journal_compliance(db, days=days, user_id=user_id)


@router.get("/logs", response_model=list[ActivityLogOut])
def logs(
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    """Journal d'activite : qui a fait quoi, quand."""
    query = db.query(ActivityLog)
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)
    if role:
        query = query.filter(ActivityLog.role == role)
    if action:
        query = query.filter(ActivityLog.action == action)
    return query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).all()


# --------------------------------------------------------------------------
# Sources de la veille
# --------------------------------------------------------------------------
@router.get("/sources", response_model=list[SourceHealthOut])
def sources_health(db: Session = Depends(get_db), current: User = Depends(admin_only)):
    """Tous les sites de la veille : nombre d'avis recuperes et etat de la
    derniere collecte, pour reperer ceux qui ne remontent plus rien."""
    today_iso = date.today().isoformat()
    open_expr = or_(Tender.deadline_iso.is_(None), Tender.deadline_iso >= today_iso)
    rows = db.query(
        Tender.source_id,
        func.count(Tender.id),
        func.sum(case((Tender.is_relevant.is_(True), 1), else_=0)),
        func.sum(case((open_expr, 1), else_=0)),
        func.max(Tender.scraped_at),
    ).group_by(Tender.source_id).all()
    counts = {sid: (total, relevant or 0, opened or 0, last) for sid, total, relevant, opened, last in rows}
    runs = {run.source_id: run for run in db.query(SourceRun).all()}

    out = []
    for source in SOURCES:
        sid = source["id"]
        total, relevant, opened, last_item_at = counts.get(sid, (0, 0, 0, None))
        run = runs.get(sid)
        has_scraper = sid in ACTIVE_SCRAPERS_BY_ID

        if not has_scraper:
            health = "sans_scraper"
        elif run is None:
            # Avis collectes avant la mise en place de ce suivi : on s'en tient a la base.
            health = "ok" if total else "jamais"
        elif run.last_status == "error":
            health = "erreur"
        elif run.last_total_found == 0:
            health = "vide"
        else:
            health = "ok"

        out.append(SourceHealthOut(
            id=sid, name=source["name"], url=source["url"], zone=source["zone"],
            has_scraper=has_scraper,
            tender_count=total, relevant_count=relevant, open_count=opened,
            last_item_at=last_item_at,
            last_run_at=run.last_run_at if run else None,
            last_status=run.last_status if run else None,
            last_error=run.last_error if run else None,
            last_total_found=run.last_total_found if run else 0,
            last_new_items=run.last_new_items if run else 0,
            last_success_at=run.last_success_at if run else None,
            health=health,
        ))
    return out


# --------------------------------------------------------------------------
# Comptes
# --------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_email(value: Optional[str]) -> Optional[str]:
    """Adresse normalisee, None si vide ; 400 si elle est manifestement invalide."""
    email = (value or "").strip().lower()
    if not email:
        return None
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide.")
    return email


@router.post("/test-email")
def send_test_email(current: User = Depends(admin_only)):
    """Envoie un e-mail d'essai a l'administrateur connecte, pour verifier la configuration."""
    if not notifications.is_configured():
        raise HTTPException(status_code=400, detail="Aucun service d'envoi d'e-mails n'est configuré sur le serveur.")
    if not current.email:
        raise HTTPException(status_code=400, detail="Renseignez d'abord une adresse e-mail sur votre compte.")
    try:
        notifications.send_email(
            [current.email],
            "Test d'envoi — Veille Appels d'Offres",
            "Les notifications par e-mail fonctionnent.",
            "<p>Les notifications par e-mail fonctionnent.</p>",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Échec de l'envoi : {exc}")
    return {"sent_to": current.email}

@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), current: User = Depends(admin_only)):
    return [user_out(u) for u in db.query(User).order_by(User.role, User.username).all()]


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreateIn,
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Rôle inconnu. Rôles possibles : {', '.join(ROLES)}")

    username = payload.username.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Cet identifiant est déjà utilisé.")

    user = User(
        username=username,
        full_name=payload.full_name,
        email=_clean_email(payload.email),
        role=payload.role,
        password_hash=auth.hash_password(payload.password),
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    auth.log_activity(
        db, current, "creation_compte",
        target_type="user", target_id=user.id,
        detail=f"{username} ({ROLE_LABELS.get(payload.role, payload.role)})",
    )
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    db: Session = Depends(get_db),
    current: User = Depends(admin_only),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable.")

    changes = []
    if payload.full_name is not None:
        user.full_name = payload.full_name
        changes.append("nom")

    if payload.email is not None:
        user.email = _clean_email(payload.email)
        changes.append("e-mail")

    if payload.role is not None and payload.role != user.role:
        if payload.role not in ROLES:
            raise HTTPException(status_code=400, detail=f"Rôle inconnu. Rôles possibles : {', '.join(ROLES)}")
        changes.append(f"role {user.role} -> {payload.role}")
        user.role = payload.role

    if payload.is_active is not None and payload.is_active != user.is_active:
        if not payload.is_active and user.id == current.id:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte.")
        if not payload.is_active and user.role == "admin":
            remaining = db.query(User).filter(
                User.role == "admin", User.is_active.is_(True), User.id != user.id
            ).count()
            if remaining == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Impossible de désactiver le dernier administrateur actif.",
                )
        changes.append("actif" if payload.is_active else "desactive")
        user.is_active = payload.is_active

    if payload.new_password:
        user.password_hash = auth.hash_password(payload.new_password)
        user.must_change_password = True
        changes.append("mot de passe reinitialise")

    auth.log_activity(
        db, current, "modification_compte",
        target_type="user", target_id=user.id,
        detail=f"{user.username} : " + (", ".join(changes) if changes else "aucun changement"),
    )
    db.commit()
    db.refresh(user)
    return user_out(user)
