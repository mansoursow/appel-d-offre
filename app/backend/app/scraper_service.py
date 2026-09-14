from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import config
from .config import SOURCE_BY_ID
from .models import Selection, SourceRun, Tender
from .scrapers.registry import ACTIVE_SCRAPERS, ACTIVE_SCRAPERS_BY_ID
from .schemas import RefreshResultOut

try:
    from dateutil import parser as date_parser
except ImportError:  # ne devrait pas arriver (python-dateutil est dans requirements.txt)
    date_parser = None


FRENCH_MONTHS = {
    "janvier": "January", "fevrier": "February", "f\u00e9vrier": "February", "mars": "March",
    "avril": "April", "mai": "May", "juin": "June", "juillet": "July",
    "aout": "August", "ao\u00fbt": "August", "septembre": "September", "octobre": "October",
    "novembre": "November", "decembre": "December", "d\u00e9cembre": "December",
}


def _translate_french_months(text: str) -> str:
    lowered = text.lower()
    for fr, en in FRENCH_MONTHS.items():
        if fr in lowered:
            # remplacement insensible a la casse, en preservant le reste de la chaine
            idx = lowered.index(fr)
            text = text[:idx] + en + text[idx + len(fr):]
            lowered = text.lower()
    return text


def parse_deadline_to_iso(deadline_text: str | None) -> str | None:
    """Convertit une date limite ecrite dans n'importe quel format rencontre
    sur les differentes sources (deja ISO, "22-Dec-25 (New York time)",
    "10 Juillet 2026", etc.) vers "YYYY-MM-DD".

    Renvoie None si la date n'a pas pu etre comprise -- dans ce cas l'offre
    reste affichee par prudence (on ne veut jamais masquer une offre a cause
    d'une date qu'on n'a pas su lire).
    """
    if not deadline_text or not date_parser:
        return None

    # Cas le plus frequent : deja au format ISO "YYYY-MM-DD" (nos scrapers
    # produisent directement ce format dans la plupart des cas).
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", deadline_text.strip())
    if m:
        return m.group(0)

    try:
        translated = _translate_french_months(deadline_text)
        dt = date_parser.parse(translated, fuzzy=True, dayfirst=True)
        return dt.date().isoformat()
    except Exception:
        return None


def _record_run(db: Session, result: RefreshResultOut) -> None:
    """Memorise le resultat de la collecte pour la page "Sources" de l'admin."""
    now = datetime.now(timezone.utc)
    run = db.get(SourceRun, result.source_id)
    if run is None:
        run = SourceRun(source_id=result.source_id)
        db.add(run)
    run.last_run_at = now
    run.last_status = result.status
    run.last_error = result.error
    run.last_total_found = result.total_found
    run.last_new_items = result.new_items
    if result.status == "ok" and result.total_found > 0:
        run.last_success_at = now
    db.commit()


def run_scraper(db: Session, source_id: str) -> RefreshResultOut:
    result = _run_scraper(db, source_id)
    try:
        _record_run(db, result)
    except Exception:  # le suivi ne doit jamais faire echouer la collecte
        db.rollback()
    return result


def _run_scraper(db: Session, source_id: str) -> RefreshResultOut:
    scraper = ACTIVE_SCRAPERS_BY_ID.get(source_id)
    meta = SOURCE_BY_ID.get(source_id, {})
    name = meta.get("name", source_id)

    if not scraper:
        return RefreshResultOut(source_id=source_id, source_name=name, status="skipped",
                                 error="Aucun scraper actif pour cette source (placeholder).")
    try:
        tender_items = scraper.fetch()
    except Exception as exc:  # une source en panne ne doit jamais casser les autres
        return RefreshResultOut(source_id=source_id, source_name=scraper.source_name,
                                 status="error", error=str(exc))

    new_count = 0
    seen_keys: set[str] = set()
    for item in tender_items:
        # un meme lot peut contenir deux fois le meme avis (ex: Banque
        # Mondiale qui liste un projet sur plusieurs lignes) : sans ce
        # garde-fou l'INSERT violerait l'unicite de dedupe_key.
        if item.dedupe_key in seen_keys:
            continue
        seen_keys.add(item.dedupe_key)
        deadline_iso = parse_deadline_to_iso(item.deadline_date)

        is_relevant = config.is_relevant_to_activity(item.title, item.description)

        existing = db.query(Tender).filter(Tender.dedupe_key == item.dedupe_key).one_or_none()
        if existing:
            existing.title = item.title
            existing.entity = item.entity
            existing.category = item.category
            existing.country = item.country
            existing.zone = item.zone
            existing.published_date = item.published_date
            existing.deadline_date = item.deadline_date
            existing.deadline_iso = deadline_iso
            existing.url = item.url
            existing.description = item.description
            existing.is_relevant = is_relevant
        else:
            db.add(Tender(
                dedupe_key=item.dedupe_key,
                source_id=item.source_id,
                source_name=item.source_name,
                title=item.title,
                entity=item.entity,
                category=item.category,
                country=item.country,
                zone=item.zone,
                published_date=item.published_date,
                deadline_date=item.deadline_date,
                deadline_iso=deadline_iso,
                url=item.url,
                description=item.description,
                is_relevant=is_relevant,
            ))
            new_count += 1
    db.commit()

    return RefreshResultOut(
        source_id=source_id,
        source_name=scraper.source_name,
        status="ok",
        new_items=new_count,
        total_found=len(tender_items),
    )


def run_all(db: Session, source_ids: list[str] | None = None) -> tuple[datetime, datetime, list[RefreshResultOut]]:
    started_at = datetime.now(timezone.utc)
    ids = source_ids or [s.source_id for s in ACTIVE_SCRAPERS]
    results = [run_scraper(db, sid) for sid in ids]
    finished_at = datetime.now(timezone.utc)
    return started_at, finished_at, results


# Avis enregistres a tort par d'anciennes versions des scrapers :
#  - "place|..." : consultations de tout PLACE, sans lien avec Expertise France ;
#  - pages de rubrique AICS prises pour des avis.
OBSOLETE_DEDUPE_KEY_PATTERNS = ["place|%"]
OBSOLETE_DEDUPE_KEYS = [
    "aics|https://dakar.aics.gov.it/aics/avvisi-di-gara-enti-terzi/?lang=fr",
    "aics|https://trasparenzadakar.aics.gov.it/pagina566_bandi-di-gara-e-contratti.html",
]


def purge_obsolete_tenders(db: Session) -> int:
    """Supprime les faux avis listes ci-dessus. Un avis sur lequel une
    decision a deja ete prise est conserve pour ne pas casser le dossier."""
    conditions = [Tender.dedupe_key.like(p) for p in OBSOLETE_DEDUPE_KEY_PATTERNS]
    conditions.append(Tender.dedupe_key.in_(OBSOLETE_DEDUPE_KEYS))
    referenced = db.query(Selection.tender_id).filter(Selection.tender_id.isnot(None))
    removed = (
        db.query(Tender)
        .filter(or_(*conditions), Tender.id.notin_(referenced))
        .delete(synchronize_session=False)
    )
    if removed:
        db.commit()
    return removed


def reclassify_relevance(db: Session) -> int:
    """Recalcule le drapeau `is_relevant` de tous les avis deja en base.

    Appele au demarrage : garantit que le filtre de pertinence reflete toujours
    la liste de mots-cles courante (config.ACTIVITY_KEYWORDS), y compris pour
    les avis collectes avant l'ajout de cette colonne ou avant un ajustement du
    profil d'activite du cabinet. Ne touche la base que si une valeur change.
    """
    changed = 0
    for tender in db.query(Tender).all():
        expected = config.is_relevant_to_activity(tender.title, tender.description)
        if tender.is_relevant != expected:
            tender.is_relevant = expected
            changed += 1
    if changed:
        db.commit()
    return changed
