"""
Authentification et gestion des roles.

Volontairement sans dependance supplementaire : le hachage des mots de passe
(PBKDF2-HMAC-SHA256) et la signature des jetons de session (HMAC-SHA256) sont
faits avec la bibliotheque standard de Python. Cela evite d'ajouter des paquets
qui demandent un compilateur sous Windows (bcrypt, cryptography...), conforme a
la contrainte "aucune dependance a compiler" du projet.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import ActivityLog, User

PBKDF2_ITERATIONS = 200_000


# --------------------------------------------------------------------------
# Cle de signature
# --------------------------------------------------------------------------
def _load_secret_key() -> bytes:
    """Recupere la cle de signature, ou la genere et la conserve sur disque.

    Conserver la cle evite de deconnecter tout le monde a chaque redemarrage du
    serveur (ce qui serait le cas avec une cle aleatoire en memoire).
    """
    if config.SECRET_KEY:
        return config.SECRET_KEY.encode("utf-8")

    path = config.SECRET_KEY_FILE
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            value = fh.read().strip()
        if value:
            return value.encode("utf-8")

    value = secrets.token_urlsafe(48)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(value)
    return value.encode("utf-8")


_SECRET_KEY = _load_secret_key()


# --------------------------------------------------------------------------
# Mots de passe
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        expected = binascii.unhexlify(digest_hex)
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), binascii.unhexlify(salt_hex), int(iterations)
        )
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(computed, expected)


# --------------------------------------------------------------------------
# Jetons de session
# --------------------------------------------------------------------------
def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(user: User) -> str:
    payload = {
        "uid": user.id,
        "usr": user.username,
        "role": user.role,
        "exp": int(time.time()) + config.TOKEN_TTL_SECONDS,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64url_encode(hmac.new(_SECRET_KEY, body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + signature


def decode_token(token: str) -> Optional[dict]:
    try:
        body, signature = token.split(".")
    except ValueError:
        return None

    expected = _b64url_encode(hmac.new(_SECRET_KEY, body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature):
        return None

    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, binascii.Error):
        return None

    if payload.get("exp", 0) < time.time():
        return None
    return payload


# --------------------------------------------------------------------------
# Dependances FastAPI
# --------------------------------------------------------------------------
def _extract_token(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    # Utile pour ouvrir un fichier directement dans un onglet du navigateur :
    # une balise <img> ou un lien ne peut pas porter d'en-tete Authorization.
    return request.query_params.get("token")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentification requise")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide")

    user = db.query(User).filter(User.id == payload["uid"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Compte introuvable ou désactivé")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Comme get_current_user mais sans erreur si personne n'est connecte."""
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user = db.query(User).filter(User.id == payload["uid"]).first()
    return user if (user and user.is_active) else None


def require_roles(*roles: str):
    """Dependance FastAPI : restreint une route a certains roles.

    L'administrateur a toujours acces (il supervise l'ensemble du processus).
    """
    allowed = set(roles) | {"admin"}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail="Votre profil ne permet pas cette action.",
            )
        return user

    return dependency


# --------------------------------------------------------------------------
# Journal d'activite
# --------------------------------------------------------------------------
def log_activity(
    db: Session,
    user: Optional[User],
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Enregistre une action dans le journal consultable par l'administrateur.

    L'appelant reste responsable du commit : la trace fait partie de la meme
    transaction que l'action tracee, donc si l'action echoue la trace disparait
    avec elle.
    """
    db.add(
        ActivityLog(
            user_id=user.id if user else None,
            username=user.username if user else None,
            role=user.role if user else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


def seed_default_users(db: Session) -> None:
    """Cree les comptes de demarrage manquants.

    Idempotent : au tout premier demarrage la base est vide et les quatre/cinq
    comptes sont crees ; sur une base deja peuplee, seuls les comptes par
    defaut ABSENTS (identifies par leur username) sont ajoutes. Cela permet
    d'introduire un nouveau profil (ex: superviseur) sans toucher aux comptes
    et mots de passe existants. Un compte desactive n'est pas recree (il existe
    toujours en base), seul un compte reellement supprime le serait.
    """
    existing_usernames = {u.username for u in db.query(User.username).all()}
    created = False
    for spec in config.DEFAULT_USERS:
        if spec["username"] in existing_usernames:
            continue
        db.add(
            User(
                username=spec["username"],
                full_name=spec["full_name"],
                role=spec["role"],
                password_hash=hash_password(spec["password"]),
                is_active=True,
                must_change_password=True,
            )
        )
        created = True
    if created:
        db.commit()
