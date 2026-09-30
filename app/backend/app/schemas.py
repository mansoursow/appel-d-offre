from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: str
    source_name: str
    title: str
    entity: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    zone: str
    published_date: Optional[str] = None
    published_iso: Optional[str] = None
    deadline_date: Optional[str] = None
    deadline_iso: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    is_relevant: bool = True
    scraped_at: Optional[datetime] = None


class TenderListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TenderOut]


class SourceOut(BaseModel):
    id: str
    name: str
    url: str
    zone: str
    status: str
    tender_count: int = 0


class RefreshResultOut(BaseModel):
    source_id: str
    source_name: str
    status: str          # ok | error | skipped
    new_items: int = 0
    total_found: int = 0
    error: Optional[str] = None


class RefreshSummaryOut(BaseModel):
    started_at: datetime
    finished_at: datetime
    results: list[RefreshResultOut]


# ---------------------------------------------------------------------------
# Relais local (voir routers/ingest.py)
# ---------------------------------------------------------------------------
class IngestItemIn(BaseModel):
    """Un avis envoye par le relais local."""

    title: str
    url: Optional[str] = None
    entity: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    zone: Optional[str] = None
    published_date: Optional[str] = None
    deadline_date: Optional[str] = None
    description: Optional[str] = None
    # Cle de dedoublonnage produite par le scraper ; recalculee si absente.
    dedupe_key: Optional[str] = None


class IngestIn(BaseModel):
    items: list[IngestItemIn] = []


class PlanItemIn(BaseModel):
    """Une ligne de plan de passation envoyee par le relais local."""

    reference: Optional[str] = None
    objet: str
    type_marche: Optional[str] = None
    mode_passation: Optional[str] = None
    date_lancement: Optional[str] = None
    date_attribution: Optional[str] = None
    autorite: str
    type_autorite: Optional[str] = None
    annee: int
    url: Optional[str] = None
    dedupe_key: str


class PlanIngestIn(BaseModel):
    items: list[PlanItemIn] = []
    # Vrai sur le dernier envoi d'une collecte complete : le serveur efface
    # alors les lignes de l'annee qui n'ont pas ete revues (realisations
    # retirees du plan par l'autorite).
    dernier_lot: bool = False
    annee: Optional[int] = None
    # Horodatage du debut de la collecte, envoye avec le dernier lot : les
    # lignes vues avant ce moment ne figurent plus dans les plans publies.
    collecte_debut: Optional[datetime] = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference: Optional[str] = None
    objet: str
    type_marche: Optional[str] = None
    mode_passation: Optional[str] = None
    date_lancement: Optional[str] = None
    date_attribution: Optional[str] = None
    autorite: str
    type_autorite: Optional[str] = None
    annee: int
    url: Optional[str] = None
    is_relevant: bool = True


class PlanListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PlanOut]


class PlanFacetsOut(BaseModel):
    """De quoi remplir les listes deroulantes de la page Plans."""

    annees: list[int] = []
    types_autorite: list[str] = []
    autorites: list[str] = []
    types_marche: list[str] = []
    total: int = 0
    derniere_collecte: Optional[datetime] = None
