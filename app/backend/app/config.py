"""
Configuration centrale de l'application.

Contient notamment le REGISTRE DES SOURCES : la liste des ~24 sites + LinkedIn
mentionnes par l'utilisateur. Chaque source a un statut :
  - "active"      : un scraper Python reel est branche (voir app/scrapers/)
  - "placeholder" : la source est repertoriee et visible dans l'UI/API mais
                     aucun scraper n'est encore ecrit. Ajouter un scraper reel
                     est ensuite juste une question de creer un fichier dans
                     app/scrapers/ et de l'enregistrer dans registry.py.

zone possibles : "senegal", "uemoa", "international"
(UEMOA = Benin, Burkina Faso, Cote d'Ivoire, Guinee-Bissau, Mali, Niger,
 Senegal, Togo -- Senegal a sa propre zone dans l'UI car l'utilisateur veut
 une colonne dediee).
"""

UEMOA_COUNTRIES = [
    "Senegal",
    "Mali",
    "Cote d'Ivoire",
    "Cote d Ivoire",
    "Ivory Coast",
    "Benin",
    "Burkina Faso",
    "Niger",
    "Togo",
    "Guinea-Bissau",
    "Guinee-Bissau",
]

# Pays "sous-region" au sens large utilise par l'utilisateur (UEMOA + voisins
# cites explicitement dans sa liste de sources : Guinee Conakry).
SOUS_REGION_COUNTRIES = UEMOA_COUNTRIES + ["Guinea", "Guinee", "Guinee Conakry"]

SOURCES = [
    # --- Organisations internationales / bailleurs ---
    {"id": "pnud", "name": "PNUD - UNDP", "url": "https://procurement-notices.undp.org/",
     "zone": "international", "status": "active"},
    {"id": "ungm", "name": "ONU - UNGM", "url": "https://www.ungm.org/",
     "zone": "international", "status": "active"},
    {"id": "ted_ue", "name": "Union Europeenne (TED)", "url": "https://ted.europa.eu/",
     "zone": "international", "status": "active"},
    {"id": "worldbank", "name": "Banque Mondiale", "url": "https://projects.worldbank.org/",
     "zone": "international", "status": "active"},
    {"id": "isdb", "name": "Banque Islamique de Developpement", "url": "https://www.isdb.org/project-procurement/fr/appels-doffres",
     "zone": "international", "status": "active"},
    {"id": "boad", "name": "BOAD", "url": "https://www.boad.org/fr",
     "zone": "uemoa", "status": "active"},
    {"id": "bceao", "name": "BCEAO", "url": "https://www.bceao.int",
     "zone": "uemoa", "status": "active"},
    {"id": "afd_dgmarket", "name": "Cooperation internationale (AFD/DgMarket)", "url": "https://afd.dgmarket.com/",
     "zone": "international", "status": "active"},
    # Expertise France publie sur PLACE (marches-publics.gouv.fr), scrape de la
    # liste "toutes les consultations" de la plateforme.
    {"id": "expertise_france", "name": "Expertise France", "url": "https://marches-publics.gouv.fr",
     "zone": "international", "status": "active"},
    # Le portail GIZ (cosinex) exige JavaScript : les avis GIZ sont recuperes
    # via l'API officielle TED (ou la GIZ publie ses appels d'offres).
    {"id": "giz", "name": "GIZ", "url": "https://ausschreibungen.giz.de/",
     "zone": "international", "status": "active"},
    {"id": "luxdev", "name": "LuxDev", "url": "https://luxdev.lu/fr",
     "zone": "international", "status": "active"},
    # AICS Dakar publie peu et irregulierement : 0 resultat est normal.
    {"id": "aics_dakar", "name": "AICS Dakar", "url": "https://dakar.aics.gov.it/fr",
     "zone": "senegal", "status": "active"},

    # --- Senegal ---
    {"id": "lesoleil", "name": "Le Soleil", "url": "https://lesoleil.sn/",
     "zone": "senegal", "status": "active"},
    {"id": "senoffre", "name": "Sen Offre", "url": "https://senoffre.com/",
     "zone": "senegal", "status": "active"},
    # Agrege aussi le portail officiel marchespublics.sn (utile quand il est en panne).
    {"id": "marchesdusenegal", "name": "Marche du Senegal", "url": "https://marchesdusenegal.com/",
     "zone": "senegal", "status": "active"},
    # Portail officiel : serveur regulierement indisponible (connexions coupees).
    # Le scraper est pret et remontera les avis des que le site repond.
    {"id": "marchespublics_sn", "name": "Marche public Senegal", "url": "http://www.marchespublics.sn/",
     "zone": "senegal", "status": "active"},
    {"id": "adepme", "name": "Senegal PME (ADEPME)", "url": "https://marches.senegalpme.sn/",
     "zone": "senegal", "status": "active"},
    {"id": "j360", "name": "J360", "url": "https://www.j360.info/",
     "zone": "senegal", "status": "active"},

    # --- Sous-region UEMOA ---
    {"id": "marchespublics_ci", "name": "Cote d'Ivoire Marche public (officiel)", "url": "https://marchespublics.ci/appel_offre",
     "zone": "uemoa", "status": "active"},
    {"id": "arcop_ci", "name": "ARCOP Cote d'Ivoire", "url": "https://arcop.ci/",
     "zone": "uemoa", "status": "active"},
    # Le site officiel affiche "Site en Construction" (verifie 13/07/2026) :
    # rien a scraper tant qu'il n'est pas remis en ligne.
    {"id": "dgcmp_guinee", "name": "DGCMP Guinee Conakry", "url": "https://www.dgcmp.mef.gov.gn/appels-doffres/",
     "zone": "uemoa", "status": "placeholder"},
    {"id": "malipages", "name": "Mali Pages", "url": "https://www.malipages.com/avis-appels-offres/",
     "zone": "uemoa", "status": "active"},
    {"id": "dgmp_mali", "name": "Site officiel Mali (DGMP)", "url": "https://www.dgmp.gouv.ml/",
     "zone": "uemoa", "status": "active"},
    # Via l'API publique api.marches-publics.bj (le portail est une SPA Angular).
    {"id": "benin", "name": "Site officiel Benin", "url": "https://marches-publics.bj/appels-doffres",
     "zone": "uemoa", "status": "active"},

    # --- Reseaux sociaux ---
    {"id": "linkedin", "name": "LinkedIn (via recherche Google)", "url": "https://www.linkedin.com/",
     "zone": "international", "status": "active"},
]

SOURCE_BY_ID = {s["id"]: s for s in SOURCES}

# HTTP
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 20

# Optionnel : cles API pour la recherche Google (LinkedIn dorking).
# A renseigner via variables d'environnement, sinon fallback DuckDuckGo (sans cle).
# Ordre de priorite utilise par linkedin.py : Serper > SerpApi > Google CSE > DuckDuckGo.
import os
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")

# Google Programmable Search Engine (Custom Search JSON API) - solution OFFICIELLE
# et gratuite (100 requetes/jour) pour interroger Google sans se connecter a un
# compte et sans scraper directement google.com (ce qui serait bloque/CAPTCHA).
# Creation : https://programmablesearchengine.google.com/ (activer "Rechercher
# sur tout le Web") puis cle API sur https://console.cloud.google.com/apis/credentials
GOOGLE_CSE_API_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./tenders.db")


# ---------------------------------------------------------------------------
# Espace de travail interne (comptes, journaux physiques, selection, dossiers)
# ---------------------------------------------------------------------------
# Ces reglages pilotent la partie "workflow" de l'application, ajoutee au
# dessus de la veille automatique : depot quotidien des photos de journaux par
# l'assistante, choix des avis a soumissionner, puis depot des offres technique
# et financiere avant la date limite.

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dossier ou sont stockes les fichiers envoyes (photos de journaux, offres).
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(_BACKEND_DIR, "uploads"))

# Cle de signature des jetons de session. Si elle n'est pas fournie par
# l'environnement, elle est generee une fois puis conservee dans un fichier :
# ainsi les utilisateurs restent connectes apres un redemarrage du serveur.
SECRET_KEY_FILE = os.environ.get("SECRET_KEY_FILE", os.path.join(_BACKEND_DIR, ".secret_key"))
SECRET_KEY = os.environ.get("SECRET_KEY", "")

# Duree de validite d'une session (par defaut 12 heures).
TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", 12 * 3600))

# Jours ou l'assistante doit deposer les journaux du jour (0 = lundi ... 6 =
# dimanche). Par defaut lundi -> samedi, la presse quotidienne ne paraissant
# pas le dimanche. Modifiable via JOURNAL_WORKING_DAYS="0,1,2,3,4" par exemple.
JOURNAL_WORKING_DAYS = [
    int(d) for d in os.environ.get("JOURNAL_WORKING_DAYS", "0,1,2,3,4,5").split(",") if d.strip() != ""
]

# Nombre de jours avant la date limite a partir duquel un dossier incomplet
# (offre technique ou financiere manquante) est signale comme urgent a l'admin.
DOC_ALERT_DAYS_BEFORE_DEADLINE = int(os.environ.get("DOC_ALERT_DAYS_BEFORE_DEADLINE", 3))

# ---------------------------------------------------------------------------
# Mise en production
# ---------------------------------------------------------------------------
# Origines autorisees a appeler l'API depuis un navigateur (CORS).
# En developpement le frontend Vite tourne sur un autre port que l'API, il faut
# donc l'autoriser explicitement. En production, quand le backend sert lui-meme
# le frontend compile, tout part de la meme origine et CORS ne sert plus a
# rien : laisser la valeur par defaut suffit. Pour autoriser un domaine tiers,
# renseigner CORS_ORIGINS="https://veille.adoc-consulting.com" (plusieurs
# origines separees par des virgules).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Dossier du frontend compile (`npm run build` produit frontend/dist). S'il
# existe, l'API le sert directement : une seule adresse pour les utilisateurs,
# et plus aucun probleme de CORS ni de configuration d'URL cote navigateur.
FRONTEND_DIST = os.environ.get(
    "FRONTEND_DIST",
    os.path.join(os.path.dirname(_BACKEND_DIR), "frontend", "dist"),
)

# Taille maximale acceptee pour un fichier envoye (photos, offres).
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", 25))

# Extensions autorisees
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf"}
ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar", ".jpg", ".jpeg", ".png"}

# Comptes crees automatiquement au tout premier demarrage (base vide).
# Les mots de passe doivent etre changes des la premiere connexion :
# l'API renvoie must_change_password=true tant que ce n'est pas fait.
DEFAULT_USERS = [
    {"username": "admin", "full_name": "Administrateur", "role": "admin", "password": "admin123"},
    {"username": "assistante", "full_name": "Assistante de direction", "role": "assistante", "password": "assistante123"},
    {"username": "selection", "full_name": "Responsable sélection", "role": "selectionneur", "password": "selection123"},
    {"username": "superviseur", "full_name": "Superviseur", "role": "superviseur", "password": "superviseur123"},
    {"username": "montage", "full_name": "Responsable montage de dossier", "role": "monteur", "password": "montage123"},
]

# selectionneur ET superviseur peuvent retenir/ecarter un avis (comme l'admin).
ROLES = ["admin", "assistante", "selectionneur", "superviseur", "monteur"]
ROLE_LABELS = {
    "admin": "Administrateur",
    "assistante": "Assistante (journaux)",
    "selectionneur": "Sélection des avis",
    "superviseur": "Superviseur",
    "monteur": "Montage des dossiers",
}

# Profils autorises a retenir/ecarter un avis (en plus de l'admin, qui a
# toujours acces). Sert cote back (require_roles) et de reference cote front.
ROLES_CAN_SELECT = ["selectionneur", "superviseur"]


# ===========================================================================
# PROFIL D'ACTIVITE DU CABINET — filtrage de pertinence de la veille
# ===========================================================================
# Le cabinet est un CABINET D'AUDIT / CONSEIL. Les sources publiques publient
# de tout (materiel, vehicules, travaux BTP, fournitures, denrees...). Par
# defaut, l'interface n'affiche donc que les avis dont l'OBJET releve de son
# activite : audit, comptabilite, conseil, etudes, evaluation, formation,
# assistance technique, prestations intellectuelles, controle/supervision...
#
# Un avis est juge pertinent si son intitule (ou sa description) contient au
# moins un des termes ci-dessous. La comparaison est insensible a la casse et
# aux accents, et se fait sur des mots entiers (donc "formation" ne matche PAS
# "transformation", "tax" ne matche pas "taxi"). Pour elargir ou restreindre
# la veille, il suffit d'ajouter/retirer un terme dans cette liste.
import re as _re
import unicodedata as _unicodedata

ACTIVITY_KEYWORDS = [
    # --- Audit & comptabilite / finance ---
    "audit", "auditoria", "auditing",
    "commissaire aux comptes", "commissariat aux comptes",
    "certification des comptes", "certification des etats financiers",
    "comptable", "comptabilite", "comptables", "accounting", "contabilidade",
    "expertise comptable", "revision comptable", "revision des comptes",
    "fiscal", "fiscalite", "fiscale",
    "gestion financiere", "financial management", "gestion budgetaire",
    "controle de gestion", "controle interne", "controle des comptes",
    # --- Conseil / consultant / assistance ---
    # NB : "conseil" seul n'est PAS retenu -> il matcherait le nom de beaucoup
    # d'acheteurs ("Conseil regional/departemental..."). On cible le sens
    # "prestation de conseil" via des expressions.
    "consultant", "consultants", "consultance",
    "consulting", "consultancy", "consultoria", "consultor", "advisory",
    "assistance technique", "technical assistance",
    "services de conseil", "service de conseil", "mission de conseil",
    "missions de conseil", "societe de conseil", "bureau de conseil",
    "prestations de conseil", "prestation de conseil",
    "conseil juridique", "conseil fiscal", "conseil en gestion",
    "conseil en organisation", "conseil en management", "conseil strategique",
    "conseil et assistance",
    # "cabinet" seul matcherait "Cabinet du Ministre/President" (acheteur) :
    # on cible un cabinet recherche comme prestataire.
    "un cabinet", "de cabinets", "des cabinets",
    "cabinet de conseil", "cabinet conseil",
    "bureau d'etudes", "bureau d'etude", "prestataire intellectuel",
    "prestations intellectuelles", "prestation intellectuelle",
    # --- Etudes / evaluation / revue / diagnostic ---
    "etude", "etudes", "study", "studies", "estudo", "estudio",
    "evaluation", "evaluations", "evaluacion", "avaliacao", "assessment",
    "revue", "review", "mi-parcours", "mid-term", "midterm",
    "diagnostic", "capitalisation", "faisabilite", "feasibility",
    "enquete", "survey", "recensement", "cartographie", "mapping",
    "elaboration", "formulation",
    # --- Controle / supervision / suivi ---
    # "controle" seul est bruyant (controle d'acces, controle sanitaire...).
    # On cible le controle/supervision de mission ou de travaux.
    "controle des travaux", "controle et surveillance", "suivi-controle",
    "suivi et controle", "mission de controle", "bureau de controle",
    "controle technique", "controle financier", "controle qualite",
    "supervision", "suivi-evaluation", "suivi et evaluation",
    "verification", "inspection", "monitoring", "surveillance et controle",
    # --- Strategie / gouvernance / organisation ---
    "strategie", "strategy", "strategique", "plan strategique", "business plan",
    "gouvernance", "governance", "restructuration", "reorganisation",
    "maitrise d'ouvrage", "maitrise d'oeuvre",
    # --- Formation / renforcement de capacites ---
    # "formation" seul matche "centre de formation" (travaux) : on cible la
    # formation dispensee comme prestation.
    "formation de", "formation des", "formation en", "formation du",
    "session de formation", "sessions de formation", "module de formation",
    "modules de formation", "plan de formation", "atelier de formation",
    "prestataire de formation", "cabinet de formation", "bureau de formation",
    "training", "renforcement de capacites", "renforcement des capacites",
    "capacity building", "seminaire", "coaching",
    # --- Juridique ---
    "juridique", "reglementaire",
]


def _normalize_activity_text(value: str) -> str:
    """Minuscule + suppression des accents, pour une comparaison robuste."""
    if not value:
        return ""
    decomposed = _unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not _unicodedata.combining(c))
    return without_accents.lower()


# Un mot-cle matche s'il apparait en debut de mot (borne \b au debut), ce qui
# gere les pluriels/derives francais ("etude" -> "etudes", "audit" -> "audits")
# sans les faux positifs de la sous-chaine ("formation" dans "transformation").
_ACTIVITY_PATTERNS = [
    _re.compile(r"\b" + _re.escape(_normalize_activity_text(kw)))
    for kw in ACTIVITY_KEYWORDS
]


def is_relevant_to_activity(*text_parts: str) -> bool:
    """Vrai si l'un des textes fournis (titre, description...) releve de
    l'activite du cabinet (audit / conseil / etudes...)."""
    haystack = _normalize_activity_text(" ".join(p for p in text_parts if p))
    if not haystack:
        return False
    return any(pattern.search(haystack) for pattern in _ACTIVITY_PATTERNS)
