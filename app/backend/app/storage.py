"""
Enregistrement sur disque des fichiers envoyes (photos de journaux, offres).

Les fichiers ne sont jamais servis directement par un serveur de fichiers
statique : ils passent par une route authentifiee (voir routers/files.py), pour
qu'un dossier de soumission ne soit pas accessible en devinant son URL.
"""
from __future__ import annotations

import os
import re
import secrets
from typing import Iterable

from fastapi import HTTPException, UploadFile

from . import config

MAX_UPLOAD_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024


def _sanitize_name(name: str) -> str:
    """Nettoie un nom de fichier fourni par le navigateur.

    On ne garde que le nom de base (jamais de chemin) et on remplace tout ce qui
    n'est pas alphanumerique : cela neutralise les tentatives de sortie du
    dossier d'upload du type "../../etc/passwd".
    """
    base = os.path.basename(name.replace("\\", "/")).strip() or "fichier"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return cleaned[:120]


def save_upload(upload: UploadFile, subdir: str, allowed_extensions: Iterable[str]) -> dict:
    """Ecrit un fichier envoye dans UPLOAD_DIR/<subdir> et renvoie ses metadonnees.

    Le nom stocke est prefixe d'un jeton aleatoire pour eviter qu'un second
    envoi du meme nom n'ecrase le premier.
    """
    original = _sanitize_name(upload.filename or "fichier")
    extension = os.path.splitext(original)[1].lower()
    allowed = set(allowed_extensions)
    if extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Format de fichier non accepté ({extension or 'inconnu'}). "
                   f"Formats acceptés : {', '.join(sorted(allowed))}",
        )

    content = upload.file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Le fichier envoyé est vide.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux (maximum {config.MAX_UPLOAD_MB} Mo).",
        )

    target_dir = os.path.join(config.UPLOAD_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)

    stored_name = f"{secrets.token_hex(8)}_{original}"
    with open(os.path.join(target_dir, stored_name), "wb") as fh:
        fh.write(content)

    return {
        "stored_path": f"{subdir}/{stored_name}",
        "original_name": original,
        "content_type": upload.content_type,
        "size_bytes": len(content),
    }


def absolute_path(stored_path: str) -> str:
    """Chemin disque d'un fichier stocke, en refusant toute sortie de UPLOAD_DIR."""
    root = os.path.abspath(config.UPLOAD_DIR)
    full = os.path.abspath(os.path.join(root, stored_path))
    if not full.startswith(root + os.sep):
        raise HTTPException(status_code=400, detail="Chemin de fichier invalide.")
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur.")
    return full


def delete_file(stored_path: str) -> None:
    """Supprime un fichier stocke, en ignorant son absence eventuelle."""
    try:
        os.remove(absolute_path(stored_path))
    except (HTTPException, OSError):
        pass
