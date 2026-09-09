"""Connexion, session courante et changement de mot de passe."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth
from ..config import ROLE_LABELS
from ..database import get_db
from ..models import User
from ..workflow_schemas import LoginIn, LoginOut, PasswordChangeIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["authentification"])


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        role_label=ROLE_LABELS.get(user.role, user.role),
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username.strip().lower()).first()
    if not user:
        # Recherche insensible a la casse en second recours (comptes crees
        # avant la normalisation systematique des identifiants).
        user = db.query(User).filter(User.username.ilike(payload.username.strip())).first()

    if not user or not auth.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Ce compte a été désactivé par l'administrateur.")

    user.last_login_at = datetime.now(timezone.utc)
    auth.log_activity(db, user, "connexion", target_type="user", target_id=user.id)
    db.commit()

    return LoginOut(token=auth.create_token(user), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(auth.get_current_user)):
    return user_out(user)


@router.post("/password", response_model=UserOut)
def change_password(
    payload: PasswordChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(auth.get_current_user),
):
    if not auth.verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect.")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent de l'ancien.")

    user.password_hash = auth.hash_password(payload.new_password)
    user.must_change_password = False
    auth.log_activity(db, user, "changement_mot_de_passe", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/logout")
def logout(db: Session = Depends(get_db), user: User = Depends(auth.get_current_user)):
    """Trace la deconnexion. Le jeton reste valide jusqu'a son expiration ;
    c'est le navigateur qui l'oublie en le retirant du stockage local."""
    auth.log_activity(db, user, "deconnexion", target_type="user", target_id=user.id)
    db.commit()
    return {"status": "ok"}
