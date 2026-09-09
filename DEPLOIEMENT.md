# Mise en production (Railway)

L'application se déploie comme **un seul service** : l'API FastAPI sert aussi
l'interface React compilée. Une seule adresse pour les utilisateurs, pas de
configuration CORS, pas de second hébergement.

```
navigateur ──► https://veille.adoc-consulting.com
                   │
                   ├── /            → interface React (frontend/dist)
                   └── /api/...     → API FastAPI + base SQLite
                                        │
                                        └── /var/data (volume persistant)
```

---

## 1. Créer le service sur Railway

1. Sur [railway.app](https://railway.app) : *New Project* → *Deploy from
   GitHub repo* → choisir `mansoursow/appel-d-offre`.
2. Railway lit `railway.json`, détecte le `Dockerfile` et lance le premier
   build (compilation React puis installation du backend, ~3 min).
3. **Ne pas ouvrir le service au public tout de suite** : créer d'abord le
   volume (étape 2), sinon la base créée au premier démarrage vivra sur un
   disque éphémère.

## 2. Créer le volume persistant — étape à ne pas sauter

Dans le service : *Settings* → *Volumes* → *New Volume*, avec le point de
montage exact :

```
/var/data
```

Sans ce volume, Railway repart d'un système de fichiers vide à chaque
redéploiement : **comptes, mots de passe, historique de connexions, journaux
de presse et offres déposées seraient perdus à chaque mise à jour du code.**

Le `Dockerfile` pointe déjà la base, les fichiers déposés et la clé de session
vers ce dossier :

| Donnée | Chemin |
|---|---|
| Base SQLite | `/var/data/tenders.db` |
| Fichiers déposés | `/var/data/uploads` |
| Clé de signature des sessions | `/var/data/.secret_key` |

Un volume impose un seul exemplaire du service : `railway.json` fixe donc
`numReplicas: 1`. Ne pas l'augmenter — deux instances écrivant sur la même
base SQLite la corrompraient.

## 3. Variables d'environnement

Aucune n'est indispensable : le `Dockerfile` fournit les valeurs par défaut,
et la clé de signature est générée au premier démarrage puis conservée sur le
volume. Deux réglages restent recommandés (*Variables* dans le service) :

| Variable | Valeur | Pourquoi |
|---|---|---|
| `SECRET_KEY` | une chaîne aléatoire longue | Clé maîtrisée, indépendante du volume. La générer avec `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Si elle change, tout le monde est déconnecté. |
| `TOKEN_TTL_SECONDS` | `43200` | Durée d'une session (12 h). |

Railway fournit `PORT` automatiquement ; le conteneur l'utilise déjà.

## 4. Brancher le sous-domaine ADOC

1. Dans le service : *Settings* → *Networking* → *Custom Domain* → ajouter
   `veille.adoc-consulting.com`. Railway affiche une cible en
   `xxx.up.railway.app`.
2. Dans le DNS Hostinger de `adoc-consulting.com`, ajouter un **CNAME** :
   nom `veille`, valeur = la cible fournie.
3. Le certificat HTTPS est émis automatiquement une fois le DNS propagé
   (quelques minutes à quelques heures).

## 5. Premier démarrage : les comptes

Au tout premier lancement sur une base vide, cinq comptes sont créés avec des
**mots de passe temporaires** (`admin` / `admin123`,
`assistante` / `assistante123`, `selection` / `selection123`,
`superviseur` / `superviseur123`, `montage` / `montage123`).

Chacun est marqué « doit changer son mot de passe » : à la première connexion,
l'application impose le changement avant tout accès. **Se connecter en `admin`
en premier** et changer le mot de passe avant de distribuer les accès.
L'administrateur peut ensuite créer, renommer ou désactiver des comptes depuis
l'écran *Administration*.

## 6. Ce qui est enregistré

Tout est en base, rien n'est perdu au redémarrage :

| Donnée | Où | Consultable par |
|---|---|---|
| Comptes, rôles, mots de passe hachés (PBKDF2) | table `users` | admin (écran *Administration*) |
| Date et heure de dernière connexion | `users.last_login_at` | admin |
| Chaque connexion et déconnexion | table `activity_logs` | admin (*Journal d'activité*) |
| Changements de mot de passe, avis retenus/écartés, dépôts de fichiers, collectes | table `activity_logs` | admin |
| Photos de journaux, offres technique et financière | `/var/data/uploads` | selon le rôle |

Les sessions durent 12 heures, puis la reconnexion est demandée.

## 7. Sauvegardes

Railway propose des sauvegardes de volume, mais une copie hors hébergeur reste
prudente. Avec le [CLI Railway](https://docs.railway.com/guides/cli) :

```bash
railway ssh "sqlite3 /var/data/tenders.db \".backup '/tmp/sauvegarde.db'\""
```

puis récupérer le fichier. À faire au moins une fois par mois, et avant toute
mise à jour importante.

## 8. Mettre à jour l'application

Railway redéploie automatiquement à chaque `git push` sur la branche
principale. La base et les fichiers déposés vivent sur le volume : ils ne sont
pas touchés par un redéploiement.

---

## Variante : exécuter l'image Docker ailleurs (VPS, poste interne)

```bash
docker build -t veille-ao .
docker run -d --name veille-ao -p 8000:8000 \
  -v veille-donnees:/var/data \
  -e SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  veille-ao
```

Le volume `veille-donnees` joue le rôle du disque persistant. L'application
répond alors sur `http://<serveur>:8000`.

## Rappel : développement local

Le mode production (backend qui sert l'interface) ne s'active que si
`frontend/dist` existe. En développement, on garde les deux serveurs :

```bash
cd app/backend && .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
cd app/frontend && npm run dev
```
