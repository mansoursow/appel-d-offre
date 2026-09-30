"""
Plans de passation des marches publics (portail senegalais).

Deux usages :
  - depot par le relais local : POST /api/ingest/plans (jeton INGEST_TOKEN) ;
  - consultation par les utilisateurs connectes : GET /api/plans et
    /api/plans/facets (listes deroulantes de la page "Plans de passation").

Un plan dit ce qu'une autorite compte lancer dans l'annee : c'est le seul
endroit ou l'on voit venir un marche avant la publication de l'avis.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import auth, config
from ..database import get_db
from ..models import ProcurementPlan, User
from ..schemas import PlanFacetsOut, PlanIngestIn, PlanListOut, PlanOut
from .ingest import _check_token

router = APIRouter(prefix="/api", tags=["plans de passation"])


# --------------------------------------------------------------------------
# Depot par le relais local
# --------------------------------------------------------------------------
@router.post("/ingest/plans")
def ingest_plans(
    payload: PlanIngestIn,
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    db: Session = Depends(get_db),
):
    """Enregistre un lot de lignes de plan. Le relais envoie la collecte par
    paquets ; le dernier lot declenche le menage des lignes disparues."""
    _check_token(x_ingest_token)

    nouveaux = 0
    vus_maintenant = datetime.now(timezone.utc)
    # Une meme reference peut apparaitre deux fois dans un plan revise :
    # sans ce garde-fou l'INSERT violerait l'unicite de dedupe_key.
    deja_vues: set[str] = set()
    for item in payload.items:
        if item.dedupe_key in deja_vues:
            continue
        deja_vues.add(item.dedupe_key)
        is_relevant = config.is_relevant_to_activity(item.objet, item.type_marche)
        existant = (
            db.query(ProcurementPlan)
            .filter(ProcurementPlan.dedupe_key == item.dedupe_key)
            .one_or_none()
        )
        valeurs = dict(
            reference=item.reference,
            objet=item.objet,
            type_marche=item.type_marche,
            mode_passation=item.mode_passation,
            date_lancement=item.date_lancement,
            date_attribution=item.date_attribution,
            autorite=item.autorite,
            type_autorite=item.type_autorite,
            annee=item.annee,
            url=item.url,
            is_relevant=is_relevant,
        )
        if existant:
            for champ, valeur in valeurs.items():
                setattr(existant, champ, valeur)
            existant.collected_at = vus_maintenant
        else:
            db.add(ProcurementPlan(dedupe_key=item.dedupe_key, collected_at=vus_maintenant, **valeurs))
            nouveaux += 1
    db.commit()

    supprimes = 0
    if payload.dernier_lot and payload.annee and payload.collecte_debut:
        # Les realisations retirees d'un plan revise ne doivent pas rester
        # affichees : on efface celles que cette collecte n'a pas revues.
        supprimes = (
            db.query(ProcurementPlan)
            .filter(
                ProcurementPlan.annee == payload.annee,
                ProcurementPlan.collected_at < payload.collecte_debut,
            )
            .delete(synchronize_session=False)
        )
        db.commit()

    total = db.query(ProcurementPlan).count()
    return {"recus": len(payload.items), "nouveaux": nouveaux, "supprimes": supprimes, "total": total}


# --------------------------------------------------------------------------
# Consultation
# --------------------------------------------------------------------------
@router.get("/plans", response_model=PlanListOut)
def list_plans(
    annee: Optional[int] = None,
    autorite: Optional[str] = None,
    type_autorite: Optional[str] = None,
    type_marche: Optional[str] = None,
    q: Optional[str] = Query(None, description="Recherche dans l'objet ou la reference"),
    relevant_only: bool = Query(True, description="N'afficher que ce qui releve de l'activite du cabinet"),
    a_venir: bool = Query(False, description="Uniquement les lancements encore a venir"),
    from_date: Optional[str] = Query(None, alias="from", description="Lancement prevu a partir de (AAAA-MM-JJ)"),
    to_date: Optional[str] = Query(None, alias="to", description="Lancement prevu jusqu'a (AAAA-MM-JJ)"),
    sort: str = Query("lancement", description="lancement | lancement_desc | autorite"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    query = db.query(ProcurementPlan)
    if annee:
        query = query.filter(ProcurementPlan.annee == annee)
    if autorite:
        query = query.filter(ProcurementPlan.autorite == autorite)
    if type_autorite:
        query = query.filter(ProcurementPlan.type_autorite == type_autorite)
    if type_marche:
        query = query.filter(ProcurementPlan.type_marche == type_marche)
    if relevant_only:
        query = query.filter(ProcurementPlan.is_relevant.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(ProcurementPlan.objet.ilike(like), ProcurementPlan.reference.ilike(like)))
    if a_venir:
        aujourdhui = datetime.now(timezone.utc).date().isoformat()
        query = query.filter(ProcurementPlan.date_lancement >= aujourdhui)
    if from_date:
        query = query.filter(ProcurementPlan.date_lancement >= from_date)
    if to_date:
        query = query.filter(ProcurementPlan.date_lancement <= to_date)

    if sort == "lancement_desc":
        ordre = [ProcurementPlan.date_lancement.desc().nullslast(), ProcurementPlan.id.desc()]
    elif sort == "autorite":
        ordre = [ProcurementPlan.autorite.asc(), ProcurementPlan.date_lancement.asc().nullslast()]
    else:
        ordre = [ProcurementPlan.date_lancement.asc().nullslast(), ProcurementPlan.id.asc()]

    total = query.count()
    items = query.order_by(*ordre).offset((page - 1) * page_size).limit(page_size).all()
    return PlanListOut(total=total, page=page, page_size=page_size, items=items)


@router.get("/plans/facets", response_model=PlanFacetsOut)
def plans_facets(
    annee: Optional[int] = None,
    relevant_only: bool = True,
    db: Session = Depends(get_db),
    current: User = Depends(auth.get_current_user),
):
    """Valeurs disponibles pour les filtres, limitees a l'annee choisie."""
    base = db.query(ProcurementPlan)
    if relevant_only:
        base = base.filter(ProcurementPlan.is_relevant.is_(True))

    annees = [a for (a,) in db.query(ProcurementPlan.annee).distinct().order_by(ProcurementPlan.annee.desc()).all()]
    filtre_annee = base.filter(ProcurementPlan.annee == annee) if annee else base

    def valeurs(colonne):
        return [
            v for (v,) in filtre_annee.with_entities(colonne).distinct().order_by(colonne.asc()).all()
            if v
        ]

    return PlanFacetsOut(
        annees=annees,
        types_autorite=valeurs(ProcurementPlan.type_autorite),
        autorites=valeurs(ProcurementPlan.autorite),
        types_marche=valeurs(ProcurementPlan.type_marche),
        total=filtre_annee.count(),
        derniere_collecte=db.query(func.max(ProcurementPlan.collected_at)).scalar(),
    )
