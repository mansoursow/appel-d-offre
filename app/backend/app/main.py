from __future__ import annotations

import logging
import os
from datetime import date
from typing import Optional

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import config, notifications, price_service, scraper_service
from .auth import get_current_user, log_activity, seed_default_users
from .config import SOURCES, SOURCE_BY_ID
from .database import Base, SessionLocal, engine, get_db, run_lightweight_migrations
from .models import Tender
from .routers import admin as admin_router
from .routers import auth_routes, files, journal, prices, selection
from .schemas import TenderListOut, TenderOut, SourceOut, RefreshSummaryOut

Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

# Comptes de demarrage (admin / assistante / selection / montage) crees une
# seule fois, si la table des utilisateurs est encore vide.
with SessionLocal() as _session:
    seed_default_users(_session)
    scraper_service.purge_obsolete_tenders(_session)
    # Recalcule la pertinence metier de tous les avis deja en base, pour que le
    # filtre "avis lies a notre activite" reflete toujours le profil courant.
    scraper_service.reclassify_relevance(_session)
    # Historique des prix des marches passes (classeur des MI et PTF). Seuls
    # les marches absents sont ajoutes : un classeur plus recent envoye par
    # l'administrateur n'est pas ecrase au redeploiement.
    price_service.seed_price_references(_session)

# Dossier de stockage des fichiers envoyes (photos de journaux, offres).
os.makedirs(config.UPLOAD_DIR, exist_ok=True)

if not config.PERSISTENT_STORAGE:
    logging.getLogger("uvicorn.error").critical(
        "AUCUN VOLUME PERSISTANT sur Railway : la base et les fichiers seront "
        "effaces au prochain redeploiement. Attacher un volume sur /var/data."
    )

app = FastAPI(title="Veille Appels d'Offres - Senegal & UEMOA", version="0.2.0")

# En production le frontend compile est servi par cette meme application
# (voir la fin du fichier) : tout vient donc de la meme origine. CORS ne sert
# qu'au developpement (Vite sur le port 5173) ou a un frontend heberge
# ailleurs, auquel cas on renseigne CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_routes.router)
app.include_router(journal.router)
app.include_router(selection.router)
app.include_router(files.router)
app.include_router(prices.router)
app.include_router(admin_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "stockage_persistant": config.PERSISTENT_STORAGE}


@app.get("/api/config")
def public_config():
    """Reglages utiles au frontend (libelles des roles, jours ouvres...)."""
    return {
        "roles": config.ROLES,
        "admin_roles": config.ADMIN_ROLES,
        "role_labels": config.ROLE_LABELS,
        "journal_working_days": config.JOURNAL_WORKING_DAYS,
        "doc_alert_days_before_deadline": config.DOC_ALERT_DAYS_BEFORE_DEADLINE,
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "email_enabled": notifications.is_configured(),
    }


@app.get("/api/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    from sqlalchemy import func
    rows = db.query(Tender.source_id, func.count(Tender.id)).group_by(Tender.source_id).all()
    count_by_source = {sid: c for sid, c in rows}

    out = []
    for s in SOURCES:
        out.append(SourceOut(
            id=s["id"], name=s["name"], url=s["url"], zone=s["zone"], status=s["status"],
            tender_count=count_by_source.get(s["id"], 0),
        ))
    return out


@app.get("/api/tenders", response_model=TenderListOut)
def list_tenders(
    zone: Optional[str] = Query(None, description="senegal | uemoa | international"),
    category: Optional[str] = Query(None, description="appel_offre | ami | autre"),
    source_id: Optional[str] = None,
    q: Optional[str] = Query(None, description="Recherche texte libre (titre / entite)"),
    only_active: bool = Query(
        True,
        description="Si vrai (defaut), masque les offres dont la date limite est deja passee.",
    ),
    relevant_only: bool = Query(
        True,
        description="Si vrai (defaut), n'affiche que les avis lies a l'activite du "
                    "cabinet (audit / conseil / etudes...). Mettre a false pour tout voir.",
    ),
    sort: str = Query(
        "deadline",
        description="deadline (echeance la plus proche d'abord, defaut) | "
                    "deadline_desc (echeance la plus lointaine) | "
                    "published (publication la plus recente)",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Tender)
    if zone:
        query = query.filter(Tender.zone == zone)
    if category:
        query = query.filter(Tender.category == category)
    if source_id:
        query = query.filter(Tender.source_id == source_id)
    if relevant_only:
        query = query.filter(Tender.is_relevant.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Tender.title.ilike(like), Tender.entity.ilike(like)))
    if only_active:
        today_iso = date.today().isoformat()
        # On garde une offre si sa date limite est inconnue (prudence : on ne
        # veut pas masquer une offre juste parce qu'on n'a pas su lire sa date)
        # OU si cette date limite n'est pas encore depassee.
        query = query.filter(or_(Tender.deadline_iso.is_(None), Tender.deadline_iso >= today_iso))

    # Tri. deadline_iso est normalise "YYYY-MM-DD" : le tri lexical correspond
    # au tri chronologique. Les avis sans date limite connue passent en dernier.
    if sort == "published":
        order_by = [Tender.published_date.desc().nullslast(), Tender.id.desc()]
    elif sort == "deadline_desc":
        order_by = [Tender.deadline_iso.desc().nullslast(), Tender.id.desc()]
    else:  # "deadline" (defaut) : echeance la plus proche d'abord
        order_by = [Tender.deadline_iso.asc().nullslast(), Tender.id.desc()]

    total = query.count()
    items = (
        query.order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return TenderListOut(total=total, page=page, page_size=page_size, items=items)


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    by_zone = dict(db.query(Tender.zone, func.count(Tender.id)).group_by(Tender.zone).all())
    by_category = dict(db.query(Tender.category, func.count(Tender.id)).group_by(Tender.category).all())
    total = db.query(Tender).count()
    return {"total": total, "by_zone": by_zone, "by_category": by_category}


@app.post("/api/refresh", response_model=RefreshSummaryOut)
def refresh(
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current=Depends(get_current_user),
):
    """Lance la collecte. Reserve aux utilisateurs connectes : l'operation
    interroge une vingtaine de sites externes et doit rester tracee."""
    if source_id and source_id not in SOURCE_BY_ID:
        raise HTTPException(status_code=404, detail="Source inconnue")
    ids = [source_id] if source_id else None
    started_at, finished_at, results = scraper_service.run_all(db, ids)

    new_items = sum(r.new_items for r in results)
    log_activity(
        db, current, "collecte_veille",
        detail=f"{new_items} nouvel(le)s annonce(s) sur {len(results)} source(s)"
               + (f" (source : {source_id})" if source_id else ""),
    )
    db.commit()
    return RefreshSummaryOut(started_at=started_at, finished_at=finished_at, results=results)


# ===========================================================================
# FRONTEND COMPILE
# ===========================================================================
# Si `frontend/dist` existe (produit par `npm run build`), l'API sert aussi
# l'interface : une seule adresse et un seul service a deployer. En
# developpement ce dossier n'existe pas, Vite prend le relais sur le port 5173
# et ce bloc est simplement ignore.
_INDEX_HTML = os.path.join(config.FRONTEND_DIST, "index.html")

if os.path.isfile(_INDEX_HTML):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(config.FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        """Renvoie l'interface React pour toute adresse qui n'est pas une API.

        Un fichier reellement present dans `dist` (favicon, image de fond...)
        est servi tel quel ; sinon on renvoie index.html pour que le routage
        cote navigateur fonctionne meme sur un rechargement de page.
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Route inconnue")

        candidate = os.path.normpath(os.path.join(config.FRONTEND_DIST, full_path))
        root = os.path.abspath(config.FRONTEND_DIST)
        if (
            full_path
            and os.path.abspath(candidate).startswith(root + os.sep)
            and os.path.isfile(candidate)
        ):
            return FileResponse(candidate)

        # index.html ne doit jamais etre garde en cache : c'est lui qui pointe
        # vers les fichiers JS/CSS de la version courante. Sans cet en-tete, un
        # navigateur continue d'afficher l'ancienne interface apres un
        # deploiement. Les fichiers de /assets portent un hash dans leur nom et
        # peuvent, eux, rester en cache.
        return FileResponse(_INDEX_HTML, headers={"Cache-Control": "no-cache"})
