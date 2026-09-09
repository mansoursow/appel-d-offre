# Veille Appels d'Offres — Sénégal & UEMOA

Application de veille qui agrège les Appels d'Offres et Avis à Manifestation
d'Intérêt (AMI) publiés par ~24 sources (Sénégal, sous-région UEMOA,
bailleurs internationaux) + une recherche LinkedIn via Google dorking.

La veille automatique est complétée par un **espace de travail interne** :
relevé quotidien de la presse papier par l'assistante, choix des avis sur
lesquels soumissionner, puis dépôt des offres technique et financière avant
l'échéance — le tout tracé et supervisé par un administrateur.

L'interface reprend la **charte du site du cabinet ADOC** (bleu `#0A2F73`,
bleu secondaire `#3F5F99`, rouge `#BF0001`, rayons de 0,625 rem) et affiche en
filigrane le croquis du bâtiment (`frontend/src/image2.jpg`), sous un voile
clair et des halos bleus qui préservent la lisibilité du contenu.

## Architecture

```
app/
  backend/    API FastAPI + scrapers Python + base SQLite
  frontend/   Interface React (Vite)
```

- **Backend** : FastAPI + SQLAlchemy + SQLite. Chaque source a un scraper
  Python dédié dans `backend/app/scrapers/`. Un registre central
  (`backend/app/config.py`) liste les ~24 sources avec leur statut
  (`active` = scraper branché, `placeholder` = source repertoriée mais pas
  encore scrapée).
- **Frontend** : React + Vite, deux colonnes (Sénégal / Sous-région UEMOA),
  filtres (mot-clé, type d'avis), case "Masquer les offres expirées" et
  bouton "Rafraîchir" qui déclenche la collecte à la demande.

## Sources actives dans ce MVP (scraping réel) — 11 sources

| Source | Zone | Méthode |
|---|---|---|
| PNUD / UNDP (procurement-notices.undp.org) | Filtré Sénégal + UEMOA | Parsing HTML |
| Banque Mondiale | Filtré Sénégal + UEMOA | API JSON officielle |
| Banque Islamique de Développement (ISDB) | Filtré Sénégal + UEMOA | Parsing HTML paginé |
| BOAD | UEMOA | Parsing HTML paginé |
| BCEAO | UEMOA | Parsing HTML (page Marchés publics & Achats) |
| Sen Offre (senoffre.com) | Sénégal | Parsing HTML |
| Marché public Côte d'Ivoire (officiel) | Côte d'Ivoire (UEMOA) | Parsing table HTML |
| ARCOP Côte d'Ivoire | Côte d'Ivoire (UEMOA) | Parsing table HTML (AO + AMI) |
| Mali Pages (malipages.com) | Mali (UEMOA) | Parsing HTML paginé |
| Site officiel Mali (DGMP) | Mali (UEMOA) | Parsing table HTML (AO + AMI) |
| LinkedIn | Sénégal + UEMOA (détecté par mots-clés) | Recherche Google (dorking) |

### Sources restées en placeholder, et pourquoi

Certaines sources de la liste initiale n'ont pas pu être branchées avec une
simple approche `requests` + parsing HTML, pour des raisons concrètes
identifiées lors de l'exploration de chaque site :

- **UNGM, TED (UE), AFD/DgMarket, Expertise France, GIZ, LuxDev** : nécessitent
  soit une authentification/session, soit une API différente de celle testée
  (ex. TED expose une API mais avec un format de requête POST plus complexe),
  soit un rendu JavaScript côté client que le scraping HTTP simple ne peut
  pas exécuter.
- **AICS Dakar, Sénégal PME (ADEPME), J360, Marché du Sénégal
  (marchesdusenegal.com), Marché public Sénégal (marchespublics.sn), Bénin
  (marches-publics.bj)** : pages construites en JavaScript (SPA) qui
  n'exposent pas leur contenu au premier chargement HTML, ou renvoient un
  accès refusé (403) au scraping simple.
- **DGCMP Guinée** : site officiel actuellement "en construction" (aucun
  contenu à scraper pour le moment).
- **Le Soleil** : journal généraliste sans rubrique dédiée aux marchés
  publics identifiée à ce jour.

Toutes restent visibles via `/api/sources` avec `status: "placeholder"`,
prêtes à recevoir un scraper réel dès qu'une solution adaptée (ex. rendu
JavaScript via navigateur headless, accès API authentifié) sera mise en
place. Voir "Ajouter une nouvelle source" ci-dessous.

## Mise en production

Le déploiement (Railway, volume persistant, sous-domaine, comptes de départ et
sauvegardes) est décrit dans [DEPLOIEMENT.md](../DEPLOIEMENT.md) à la racine du
dépôt. En production, l'API sert elle-même l'interface compilée : un seul
service et une seule adresse.

## Lancer le backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

(`python -m uvicorn ...` est plus fiable que la commande `uvicorn` seule sous
Windows, car elle évite les soucis de PATH quand le script n'est pas dans un
environnement virtuel activé.)

L'API est alors disponible sur http://localhost:8000 (doc interactive :
http://localhost:8000/docs). La base SQLite (`tenders.db`) est créée
automatiquement au premier lancement dans `backend/`.

### Si `pip install` échoue à compiler un paquet (Windows)

Le projet n'utilise volontairement **aucune dépendance qui nécessite un
compilateur** (pas de `lxml`, BeautifulSoup utilise le parser `html.parser`
intégré à Python). Si `pip install` tente quand même de compiler un paquet
depuis les sources (erreurs `Microsoft Visual C++ 14.0 required` ou
`linker link.exe not found`), la cause la plus fréquente est une version de
Python trop récente pour laquelle certains paquets n'ont pas encore de
"wheel" précompilé pour Windows (ex. Python 3.14 fraîchement sorti). Deux
options :

1. Mettre à jour pip (`python -m pip install --upgrade pip`) puis
   réessayer — de nouvelles wheels sont publiées régulièrement.
2. Utiliser une version de Python plus établie pour ce projet, par exemple
   **Python 3.11 ou 3.12**, qui dispose de wheels précompilées pour
   l'ensemble des dépendances utilisées ici.

Si vous voyez une erreur `disk I/O error` liée à SQLite (rare, généralement
sur certains montages réseau), définissez la variable d'environnement
`DATABASE_URL` vers un chemin local, ex. :
`DATABASE_URL=sqlite:///C:/temp/tenders.db uvicorn app.main:app --reload`.

### Endpoints principaux

- `GET /api/tenders?zone=senegal|uemoa&category=appel_offre|ami&q=...&only_active=true` — liste des avis
- `GET /api/sources` — liste des 24+ sources avec leur statut et compteur
- `GET /api/stats` — compteurs globaux
- `POST /api/refresh` — lance le scraping de toutes les sources actives (ou `?source_id=xxx` pour une seule)

### Filtrage des offres expirées

Par défaut (`only_active=true`), l'API masque les offres dont la date limite
de dépôt est déjà passée par rapport à la date du jour. Cette date limite est
normalisée automatiquement (champ `deadline_iso`, format `YYYY-MM-DD`) à
partir du texte brut trouvé sur chaque site, quel que soit son format
d'origine ("22-Dec-25", "10 juillet 2026", "31/07/2026", etc.). Si la date
n'a pas pu être comprise, l'offre reste affichée par prudence plutôt que
d'être masquée à tort. Le frontend expose une case à cocher "Masquer les
offres expirées" (activée par défaut) pour piloter ce comportement ; il est
aussi possible de repasser `only_active=false` directement dans l'URL de
l'API pour tout voir, y compris les offres expirées (affichées grisées avec
un badge "Expiré" dans l'interface).

Une base de données déjà existante (créée avant l'ajout de cette
fonctionnalité) est mise à jour automatiquement au démarrage du serveur
(migration légère qui ajoute la colonne manquante) — aucune manipulation
n'est nécessaire de votre côté.

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

Ouvre http://localhost:5173. Le frontend appelle l'API sur
`http://localhost:8000` par défaut (modifiable via `.env` → `VITE_API_URL`,
voir `.env.example`).

> Note : le dossier `frontend/node_modules` présent dans ce livrable peut
> être supprimé et régénéré avec `npm install` — c'est un dossier
> d'installation, pas du code source.

## Recherche LinkedIn (Google dorking)

Le module `backend/app/scrapers/linkedin.py` interroge :
`site:linkedin.com/posts ("appel d'offres" OR "avis a manifestation
d'interet") AND ("Senegal" OR "Côte d'Ivoire" OR ...)`.

On ne scrape jamais LinkedIn ni Google directement (les deux bloquent tres
vite les requetes automatisees, CAPTCHA compris). Le module essaie, dans cet
ordre, la premiere solution disponible :

1. **Serper.dev** (`SERPER_API_KEY`) — vrais résultats Google, très fiable,
   payant à l'usage (offre d'essai gratuite à l'inscription). Le plus simple
   à mettre en place pour un usage régulier.
2. **SerpApi** (`SERPAPI_API_KEY`) — équivalent à Serper, un peu plus cher,
   supporte aussi d'autres moteurs.
3. **Google Programmable Search Engine / Custom Search JSON API**
   (`GOOGLE_CSE_API_KEY` + `GOOGLE_CSE_ID`) — **solution officielle Google,
   gratuite jusqu'à 100 requêtes/jour**. C'est la meilleure option "recherche
   Google sans compte à connecter" si vous ne voulez pas payer : configuration
   en 5 minutes, pas de scraping de google.com (donc pas de blocage/CAPTCHA).
   Étapes :
   1. Aller sur https://programmablesearchengine.google.com/ → créer un
      moteur de recherche → dans ses paramètres, activer "Rechercher sur
      tout le Web" (sinon il ne cherche que sur des sites que vous listez).
      Récupérer son **Search engine ID** (`GOOGLE_CSE_ID`).
   2. Aller sur https://console.cloud.google.com/apis/credentials → créer
      une clé API → l'activer pour l'API "Custom Search API" (à activer une
      fois sur https://console.cloud.google.com/apis/library/customsearch.googleapis.com).
      C'est votre `GOOGLE_CSE_API_KEY`.
   3. Définir les deux variables avant de lancer le backend (voir ci-dessous).
4. **DuckDuckGo HTML** (aucune clé) — fallback gratuit sans inscription,
   mais moins riche et sans garantie de fiabilité dans la durée (pas une API
   officielle). C'est le mode utilisé si aucune des options ci-dessus n'est
   configurée — c'est le cas par défaut dans ce livrable.

```bash
export SERPER_API_KEY=xxxx           # https://serper.dev
# ou
export SERPAPI_API_KEY=xxxx          # https://serpapi.com
# ou (gratuit, recommandé si vous ne voulez pas payer)
export GOOGLE_CSE_API_KEY=xxxx       # https://console.cloud.google.com/apis/credentials
export GOOGLE_CSE_ID=xxxx            # https://programmablesearchengine.google.com/
```

Sous Windows (PowerShell), remplacez `export VAR=valeur` par
`$env:VAR="valeur"` avant de lancer `python -m uvicorn ...` dans le même
terminal.

## Ajouter une nouvelle source (passer un placeholder en actif)

1. Créer `backend/app/scrapers/mon_site.py` avec une classe héritant de
   `BaseScraper` (voir `backend/app/scrapers/malipages.py` comme modèle
   simple, ou `worldbank.py` si le site a une API JSON).
2. L'ajouter à `ACTIVE_SCRAPERS` dans `backend/app/scrapers/registry.py`.
3. Passer `"status": "active"` pour cette source dans `backend/app/config.py`.

Rien d'autre à modifier : l'API, la base de données et le frontend
découvrent automatiquement la nouvelle source.

## Limites connues de ce MVP

- Les scrapers HTML reposent sur la structure actuelle des pages ; si un site
  change de gabarit, le scraper correspondant peut nécessiter un ajustement
  mineur des sélecteurs.
- Le rafraîchissement est déclenché manuellement (bouton), pas encore
  planifié automatiquement — cela pourra être ajouté ensuite (cron/Celery).
- Le design du frontend est minimal par choix, pour valider le
  fonctionnement avant de travailler l'aspect visuel.

---

# Espace de travail interne

En plus de la veille automatique, l'application couvre le circuit complet d'un
avis, depuis sa parution jusqu'au dépôt du dossier.

## Les quatre profils

| Profil | Identifiant initial | Ce qu'il fait |
|---|---|---|
| **Administrateur** | `admin` / `admin123` | Supervise tout : alertes, historiques, journal d'activité, gestion des comptes |
| **Assistante** | `assistante` / `assistante123` | Dépose chaque jour les photos des avis parus dans la presse papier, ou déclare NÉANT / RAS |
| **Sélection** | `selection` / `selection123` | Décide des avis (veille en ligne ou presse papier) sur lesquels le cabinet soumissionne |
| **Montage** | `montage` / `montage123` | Joint l'offre technique et l'offre financière avant la date limite |

Ces quatre comptes sont créés **une seule fois**, au premier démarrage sur une
base vide. Chacun doit remplacer son mot de passe initial à la première
connexion (l'application le lui impose). L'administrateur peut ensuite créer
d'autres comptes, en désactiver, ou réinitialiser un mot de passe depuis
l'onglet **Administration -> Comptes**.

> Les mots de passe sont hachés en PBKDF2-HMAC-SHA256 (200 000 itérations) et
> les sessions signées en HMAC-SHA256, avec la bibliothèque standard de Python
> uniquement : aucune dépendance à compiler n'a été ajoutée.

## 1. Journaux papier (assistante)

Onglet **Journaux papier**. Chaque jour ouvré, l'assistante :

- **joint les photos** des avis parus dans la presse (JPG, PNG, WEBP, HEIC ou
  PDF, plusieurs fichiers à la fois), en indiquant le journal et l'intitulé de
  l'avis ; **ou**
- clique sur **NÉANT** ou **RAS** si aucun avis n'est paru ce jour-là.

Un seul dépôt existe par jour et par compte. Une journée déjà déclarée
NÉANT/RAS qui reçoit finalement une photo repasse automatiquement en « avis
photographiés » ; inversement, NÉANT/RAS est refusé tant que des photos sont
attachées à la journée.

Une journée passée peut être complétée après coup (sélecteur de date), mais la
date et l'heure réelles du dépôt restent visibles par l'administrateur : un
rattrapage ne se confond jamais avec un dépôt fait à temps.

### Ce que voit l'administrateur

Onglet **Administration -> Suivi des journaux** : l'historique jour par jour
sur 15, 30, 90 ou 180 jours, avec le nombre de journées déposées, le nombre de
**journées ouvrées restées sans dépôt** (affichées en rouge) et le taux de
suivi. Chaque journée manquante remonte aussi dans **Administration ->
Alertes**.

Les jours ouvrés sont configurables : par défaut lundi -> samedi, la presse
quotidienne ne paraissant pas le dimanche (voir `JOURNAL_WORKING_DAYS`
ci-dessous). Le jour en cours n'est jamais compté comme manquant tant qu'il
n'est pas terminé.

## 2. Sélection des avis (profil « sélection »)

Le responsable sélection travaille sur les deux sources :

- onglet **Veille en ligne** : chaque avis collecté porte les boutons
  « Retenir cet avis » / « Ne pas soumissionner » ;
- onglet **Journaux papier** : les mêmes boutons sous chaque photo d'avis
  relevé dans la presse.

À la décision, une fenêtre demande la **date limite de dépôt** (pré-remplie
depuis la source quand elle a pu être lue automatiquement — sinon à saisir, car
c'est elle qui déclenche les rappels), le **responsable du montage** du dossier
et un commentaire. Un avis écarté demande son motif.

Le libellé, l'entité, l'échéance et le lien sont recopiés au moment de la
décision : le dossier interne reste lisible même si l'annonce disparaît du site
d'origine. Un même avis ne peut recevoir qu'une seule décision.

Toutes ces décisions sont horodatées et consultables par l'administrateur dans
**Administration -> Journal d'activité** (filtrable par profil et par action).

## 3. Dépôt des offres (profil « montage »)

Onglet **Dossiers**. Chaque avis retenu attend deux pièces : **offre
technique** et **offre financière** (PDF, Word, Excel, archive ou image). Tant
que les deux ne sont pas jointes, le dossier affiche son état :

| État | Signification |
|---|---|
| **En préparation** | pièce(s) manquante(s), l'échéance laisse du temps |
| **Échéance proche** | pièce(s) manquante(s) à 3 jours ou moins de la date limite |
| **En retard** | date limite dépassée, dossier toujours incomplet |
| **Dossier complet** | les deux offres sont déposées |

Un nouveau dépôt du même type remplace le précédent (correction d'un envoi
erroné) et l'ancien fichier est effacé du disque.

**Les états « Échéance proche » et « En retard » remontent automatiquement dans
les alertes de l'administrateur**, avec le nom du responsable et la liste des
pièces manquantes. C'est le filet de sécurité attendu : si l'offre n'est pas
jointe avant l'expiration, l'administrateur le voit.

## 4. Supervision (administrateur)

Onglet **Administration** :

- **Alertes** — les journées de journaux non déposées et les dossiers dont une
  offre manque à l'approche (ou au-delà) de l'échéance, classés par gravité ;
- **Suivi des journaux** — l'historique jour par jour, tous comptes ou un seul ;
- **Journal d'activité** — connexions, dépôts, déclarations NÉANT/RAS,
  décisions de sélection, dépôts et retraits d'offres, collectes de la veille,
  gestion des comptes ;
- **Comptes** — création, désactivation, réinitialisation de mot de passe.

Le compteur rouge sur l'onglet « Administration » indique le nombre d'alertes
en cours.

## Fichiers déposés

Les photos et les offres sont stockées sous `backend/uploads/`
(`journaux/AAAA-MM-JJ/...` et `dossiers/<id>/...`). Elles ne sont **jamais
servies en statique** : chaque téléchargement passe par une route authentifiée
(`/api/files/...`), pour qu'un dossier de soumission ne soit pas lisible par
quiconque devine son URL. Taille maximale par fichier : 25 Mo (configurable).

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `SECRET_KEY` | générée puis conservée dans `backend/.secret_key` | Signature des sessions |
| `TOKEN_TTL_SECONDS` | `43200` (12 h) | Durée d'une session |
| `JOURNAL_WORKING_DAYS` | `0,1,2,3,4,5` (lundi -> samedi) | Jours où le dépôt des journaux est attendu |
| `DOC_ALERT_DAYS_BEFORE_DEADLINE` | `3` | Délai à partir duquel un dossier incomplet devient « urgent » |
| `MAX_UPLOAD_MB` | `25` | Taille maximale d'un fichier envoyé |
| `UPLOAD_DIR` | `backend/uploads` | Dossier de stockage des fichiers |

## Endpoints ajoutés

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/password`, `POST /api/auth/logout`
- `GET /api/journal/today`, `GET /api/journal/entries`, `POST /api/journal/photos`,
  `POST /api/journal/status`, `DELETE /api/journal/photos/{id}`, `GET /api/journal/compliance`
- `GET /api/selections`, `POST /api/selections`, `PATCH /api/selections/{id}`,
  `POST /api/selections/{id}/documents`, `DELETE /api/documents/{id}`,
  `GET /api/users/assignable`
- `GET /api/files/journal/{id}`, `GET /api/files/document/{id}`
- `GET /api/admin/dashboard`, `/api/admin/alerts`, `/api/admin/journal-compliance`,
  `/api/admin/logs`, `/api/admin/users` (+ `POST` / `PATCH`)

La documentation interactive complète reste disponible sur
http://localhost:8000/docs.

## Mise à jour d'une installation existante

Rien de particulier : les nouvelles tables sont créées au démarrage et les
quatre comptes initiaux sont ajoutés si aucun utilisateur n'existe encore. La
base d'avis déjà collectés est conservée. Une seule dépendance a été ajoutée
(`python-multipart`, nécessaire à l'envoi de fichiers) :

```bash
cd backend
pip install -r requirements.txt
```
