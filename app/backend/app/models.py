from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Tender(Base):
    """Un avis (Appel d'offres / AMI / etc.) collecte depuis une source."""

    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)

    # Cle de dedoublonnage : identifie une annonce de maniere stable
    # meme si on relance le scraping plusieurs fois.
    dedupe_key = Column(String(500), unique=True, index=True, nullable=False)

    source_id = Column(String(50), index=True, nullable=False)
    source_name = Column(String(200), nullable=False)

    title = Column(Text, nullable=False)
    entity = Column(Text, nullable=True)          # organisme / acheteur
    category = Column(String(50), nullable=True)  # appel_offre | ami | autre
    country = Column(String(100), nullable=True, index=True)
    zone = Column(String(20), nullable=False, index=True)  # senegal | uemoa | international

    published_date = Column(String(30), nullable=True)  # texte tel que trouve sur la source
    deadline_date = Column(String(30), nullable=True)   # texte tel que trouve sur la source

    # Date limite normalisee au format ISO "YYYY-MM-DD", calculee automatiquement
    # a partir de deadline_date (voir scraper_service.py). Sert uniquement au
    # filtrage "offres encore en cours" ; peut etre NULL si la date n'a pas pu
    # etre comprise (dans ce cas l'offre reste affichee par prudence).
    deadline_iso = Column(String(10), nullable=True, index=True)

    url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Pertinence metier : True si l'objet de l'avis releve de l'activite du
    # cabinet (audit / conseil / etudes...), calcule automatiquement a partir
    # de l'intitule et de la description (voir config.is_relevant_to_activity).
    # Sert au filtre "Uniquement les avis lies a notre activite" de la veille.
    is_relevant = Column(Boolean, nullable=False, default=True, server_default="1", index=True)

    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_tender_dedupe_key"),
    )


class SourceRun(Base):
    """Resultat de la derniere collecte d'une source (une ligne par source).

    Permet a l'administrateur de reperer les sites qui ne remontent plus rien :
    scraper en erreur, site en panne, ou collecte reussie mais vide.
    """

    __tablename__ = "source_runs"

    source_id = Column(String(50), primary_key=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(20), nullable=True)   # ok | error | skipped
    last_error = Column(Text, nullable=True)
    last_total_found = Column(Integer, nullable=False, default=0)
    last_new_items = Column(Integer, nullable=False, default=0)
    # Derniere collecte ayant effectivement ramene au moins un avis.
    last_success_at = Column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Espace de travail interne : comptes, journaux physiques, selection, dossiers
# ---------------------------------------------------------------------------


class User(Base):
    """Compte utilisateur de l'application interne.

    role :
      - admin         : voit tout, gere les comptes, recoit les alertes
      - assistante    : depose chaque jour les photos des journaux (ou NEANT/RAS)
      - selectionneur : decide sur quels avis on soumissionne
      - superviseur   : peut aussi retenir/ecarter un avis (comme le selectionneur)
      - monteur       : depose les offres technique et financiere
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=True)
    # Adresse de notification (ex : un avis retenu confie a ce compte).
    email = Column(String(200), nullable=True)
    role = Column(String(30), nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    # Vrai tant que l'utilisateur n'a pas remplace le mot de passe initial.
    must_change_password = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)


class JournalEntry(Base):
    """Le depot du jour de l'assistante : les journaux papier photographies.

    Un seul enregistrement par (utilisateur, jour). Trois cas possibles :
      - status = "photos" : au moins une photo d'avis a ete jointe
      - status = "neant"  : aucun avis dans les journaux du jour (bouton NEANT)
      - status = "ras"    : rien a signaler (bouton RAS)
    L'absence d'enregistrement pour un jour ouvre = depot manquant, visible
    par l'administrateur (voir /api/admin/journal-compliance).
    """

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    entry_date = Column(String(10), index=True, nullable=False)  # "YYYY-MM-DD"
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    status = Column(String(20), nullable=False)  # photos | neant | ras
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    photos = relationship(
        "JournalPhoto", back_populates="entry", cascade="all, delete-orphan", order_by="JournalPhoto.id"
    )

    __table_args__ = (
        UniqueConstraint("entry_date", "user_id", name="uq_journal_entry_day_user"),
    )


class JournalPhoto(Base):
    """Une photo (ou un scan PDF) d'un avis paru dans un journal papier."""

    __tablename__ = "journal_photos"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("journal_entries.id"), index=True, nullable=False)
    stored_path = Column(Text, nullable=False)       # chemin relatif dans UPLOAD_DIR
    original_name = Column(Text, nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    # Informations saisies par l'assistante sur l'avis photographie
    newspaper = Column(String(200), nullable=True)   # nom du journal (Le Soleil, etc.)
    caption = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    entry = relationship("JournalEntry", back_populates="photos")


class Selection(Base):
    """Decision de soumissionner (ou non) sur un avis.

    L'avis peut venir de la veille automatique (tender_id renseigne) ou d'une
    photo de journal papier (journal_photo_id renseigne).
    """

    __tablename__ = "selections"

    id = Column(Integer, primary_key=True, index=True)

    tender_id = Column(Integer, ForeignKey("tenders.id"), index=True, nullable=True)
    journal_photo_id = Column(Integer, ForeignKey("journal_photos.id"), index=True, nullable=True)

    # Copie du libelle et de la date limite au moment de la decision : l'avis
    # source peut disparaitre du site d'origine, le dossier doit rester lisible.
    title = Column(Text, nullable=False)
    entity = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)     # appel_offre | ami | autre
    deadline_iso = Column(String(10), nullable=True, index=True)
    url = Column(Text, nullable=True)

    decision = Column(String(20), nullable=False, index=True)  # retenu | rejete
    comment = Column(Text, nullable=True)

    selected_by_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)

    # Passe a True quand les deux offres (technique + financiere) sont deposees.
    is_complete = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    selected_by = relationship("User", foreign_keys=[selected_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    documents = relationship(
        "SubmissionDocument", back_populates="selection", cascade="all, delete-orphan",
        order_by="SubmissionDocument.id",
    )


class SubmissionDocument(Base):
    """Une piece du dossier de soumission : offre technique ou financiere."""

    __tablename__ = "submission_documents"

    id = Column(Integer, primary_key=True, index=True)
    selection_id = Column(Integer, ForeignKey("selections.id"), index=True, nullable=False)
    doc_type = Column(String(20), nullable=False, index=True)  # technique | financiere
    stored_path = Column(Text, nullable=False)
    original_name = Column(Text, nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    selection = relationship("Selection", back_populates="documents")
    uploaded_by = relationship("User")


class ActivityLog(Base):
    """Journal d'activite : qui a fait quoi, quand. Consultable par l'admin.

    On duplique username/role dans la ligne pour que l'historique reste lisible
    meme si un compte est renomme ou desactive plus tard.
    """

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    username = Column(String(80), nullable=True)
    role = Column(String(30), nullable=True, index=True)
    action = Column(String(60), nullable=False, index=True)
    target_type = Column(String(40), nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
