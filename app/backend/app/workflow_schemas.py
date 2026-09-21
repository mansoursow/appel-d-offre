"""
Schemas Pydantic de l'espace de travail interne (comptes, journaux papier,
selection des avis, depot des offres, supervision).

Separe de schemas.py, qui reste dedie a la veille automatique.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------
# Comptes et session
# --------------------------------------------------------------------------
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    role_label: Optional[str] = None
    is_active: bool
    must_change_password: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    user: UserOut


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: Optional[str] = None
    email: Optional[str] = Field(default=None, max_length=200)
    role: str
    password: str = Field(min_length=6)


class UserUpdateIn(BaseModel):
    full_name: Optional[str] = None
    # Chaine vide = retirer l'adresse.
    email: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=6)


# --------------------------------------------------------------------------
# Journaux papier
# --------------------------------------------------------------------------
class JournalPhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    newspaper: Optional[str] = None
    caption: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    file_url: Optional[str] = None
    # Renseigne si une decision a deja ete prise sur cet avis papier.
    selection_id: Optional[int] = None
    selection_decision: Optional[str] = None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: str
    status: str
    note: Optional[str] = None
    user_id: int
    user_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    photos: list[JournalPhotoOut] = []


class JournalStatusIn(BaseModel):
    """Declaration "NEANT" / "RAS" pour une journee sans avis a signaler."""

    entry_date: Optional[str] = None  # defaut : aujourd'hui
    status: str                        # neant | ras
    note: Optional[str] = None


class JournalDayOut(BaseModel):
    """Etat d'une journee dans l'historique de conformite."""

    date: str
    weekday: str
    is_working_day: bool
    done: bool
    status: Optional[str] = None       # photos | neant | ras | None
    photo_count: int = 0
    user_name: Optional[str] = None
    entry_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    # Vrai si la journee est ouvree, passee, et qu'aucun depot n'a ete fait.
    is_missing: bool = False


class JournalComplianceOut(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    from_date: str
    to_date: str
    working_days: int
    days_done: int
    days_missing: int
    completion_rate: float
    today_done: bool
    days: list[JournalDayOut]


# --------------------------------------------------------------------------
# Selection des avis et depot des offres
# --------------------------------------------------------------------------
class SubmissionDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    original_name: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    uploaded_by_name: Optional[str] = None
    file_url: Optional[str] = None


class SelectionCreateIn(BaseModel):
    """Decision prise par le responsable selection sur un avis.

    L'avis vient soit de la veille automatique (tender_id), soit d'une photo de
    journal papier (journal_photo_id) : l'un des deux doit etre fourni.
    """

    tender_id: Optional[int] = None
    journal_photo_id: Optional[int] = None
    decision: str = "retenu"           # retenu | rejete
    comment: Optional[str] = None
    assigned_to_id: Optional[int] = None
    # Utilises uniquement pour un avis papier (pas de fiche source a recopier)
    title: Optional[str] = None
    entity: Optional[str] = None
    category: Optional[str] = None
    deadline_iso: Optional[str] = None
    url: Optional[str] = None


class SelectionUpdateIn(BaseModel):
    decision: Optional[str] = None
    comment: Optional[str] = None
    assigned_to_id: Optional[int] = None
    deadline_iso: Optional[str] = None


class SelectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tender_id: Optional[int] = None
    journal_photo_id: Optional[int] = None
    title: str
    entity: Optional[str] = None
    category: Optional[str] = None
    deadline_iso: Optional[str] = None
    url: Optional[str] = None
    decision: str
    comment: Optional[str] = None
    selected_by_id: int
    selected_by_name: Optional[str] = None
    assigned_to_id: Optional[int] = None
    assigned_to_name: Optional[str] = None
    is_complete: bool
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    documents: list[SubmissionDocumentOut] = []

    # Champs calcules
    has_technique: bool = False
    has_financiere: bool = False
    missing_documents: list[str] = []
    days_left: Optional[int] = None
    # complet | en_retard | urgent | en_cours | rejete
    dossier_status: str = "en_cours"


# --------------------------------------------------------------------------
# Supervision (administrateur)
# --------------------------------------------------------------------------
class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


class AlertOut(BaseModel):
    kind: str            # journal_manquant | dossier_incomplet | stockage_non_persistant
    severity: str        # critique | urgent | info
    title: str
    detail: str
    date: Optional[str] = None
    target_id: Optional[int] = None
    days_left: Optional[int] = None


class SourceHealthOut(BaseModel):
    """Etat d'un site de la veille : ce qu'on en a recupere et sa derniere collecte."""

    id: str
    name: str
    url: str
    zone: str
    has_scraper: bool
    tender_count: int = 0        # avis en base, toutes dates confondues
    relevant_count: int = 0      # dont lies a l'activite du cabinet
    open_count: int = 0          # dont date limite non depassee (ou inconnue)
    last_item_at: Optional[datetime] = None  # derniere mise a jour d'un avis
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None        # ok | error | skipped
    last_error: Optional[str] = None
    last_total_found: int = 0
    last_new_items: int = 0
    last_success_at: Optional[datetime] = None
    # ok | vide | erreur | jamais | sans_scraper
    health: str


class AdminDashboardOut(BaseModel):
    alerts: list[AlertOut]
    journal_missing_days: int
    journal_today_done: bool
    selections_retenues: int
    dossiers_incomplets: int
    dossiers_en_retard: int
    users_count: int


# --------------------------------------------------------------------------
# Historique des prix (classeur des MI et PTF)
# --------------------------------------------------------------------------
class PriceOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nom: str
    montant: Optional[int] = None          # FCFA TTC ; absent si la saisie est illisible
    montant_texte: Optional[str] = None    # texte d'origine (fourchette, mention...)
    note: Optional[int] = None             # note technique, quand elle est connue
    est_adoc: bool = False
    est_attributaire: bool = False
    # Ecart en % par rapport a l'offre ADOC du meme marche (negatif = moins cher).
    ecart_adoc_pct: Optional[float] = None


class PriceMarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    annee: int
    date: Optional[str] = None
    objet: str
    structure: Optional[str] = None
    methode: Optional[str] = None
    # Nature de la prestation : un CAC ne se compare pas a un PSD.
    nature: str = "autre"
    nature_label: str = "Autre prestation"
    attributaire: Optional[str] = None
    observations: Optional[str] = None
    participants_bruts: Optional[str] = None
    offres: list[PriceOfferOut] = []

    montant_adoc: Optional[int] = None      # ce que le cabinet a propose
    montant_gagnant: Optional[int] = None   # le prix de l'attributaire
    adoc_gagnant: bool = False
    # Rang du prix ADOC parmi les offres chiffrees (1 = le moins cher).
    rang_adoc: Optional[int] = None
    nb_offres_chiffrees: int = 0
    montant_moins_disant: Optional[int] = None   # l'offre la plus basse du marche
    adoc_moins_disant: bool = False              # ... et c'etait la notre


class CompetitorStatOut(BaseModel):
    """Ce qu'un concurrent propose d'habitude, compare a ADOC."""

    nom: str
    marches: int                            # rencontres avec un prix connu
    victoires: int
    montant_min: Optional[int] = None
    montant_max: Optional[int] = None
    montant_median: Optional[int] = None
    # Moyenne des ecarts avec ADOC sur les marches ou les deux prix sont connus.
    comparaisons: int = 0
    ecart_moyen_pct: Optional[float] = None
    moins_cher_que_adoc: int = 0


class NatureOptionOut(BaseModel):
    """Une nature de marche proposee au filtrage, avec son effectif."""

    code: str
    label: str
    marches: int


class NatureBenchmarkOut(BaseModel):
    """Repere de prix pour une nature de marche.

    Repond a la question : sur ce type de prestation, a quel niveau faut-il
    chiffrer pour etre le moins-disant ? Les montants ne sont comparables
    qu'a l'interieur d'une meme nature -- un commissariat aux comptes et un
    plan strategique n'ont pas la meme echelle de prix.
    """

    code: str
    label: str
    marches: int                             # marches de cette nature
    marches_compares: int                    # dont au moins deux prix connus
    adoc_median: Optional[int] = None        # ce que nous proposons d'habitude
    concurrent_min: Optional[int] = None     # l'offre concurrente la plus basse vue
    concurrent_median: Optional[int] = None
    # Mediane du prix le plus bas de chaque marche : le niveau a battre.
    moins_disant_median: Optional[int] = None
    fois_moins_disant: int = 0               # marches ou notre offre etait la plus basse
    victoires: int = 0                       # marches remportes par ADOC


class PriceHistoryOut(BaseModel):
    marches: list[PriceMarketOut]
    concurrents: list[CompetitorStatOut]
    reperes: list[NatureBenchmarkOut]
    annees: list[int]
    methodes: list[str]
    natures: list[NatureOptionOut]
    total_marches: int          # avant filtrage, pour situer le sous-ensemble affiche
    marches_gagnes: int         # parmi les marches affiches
