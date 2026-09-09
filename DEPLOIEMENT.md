# Mise en production

L'application se déploie comme **un seul service** : l'API FastAPI sert aussi
l'interface React compilée. Une seule adresse pour les utilisateurs, pas de
configuration CORS, pas de second hébergement à payer.

```
navigateur ──► https://veille.adoc-consulting.com
                   │
                   ├── /            → interface React (frontend/dist)
                   └── /api/...     → API FastAPI + base SQLite
```

---

## 1. Déployer sur Render

1. **Créer le service.** Sur [render.com](https://render.com) : *New* →
   *Web Service* → connecter le dépôt GitHub. Render détecte `render.yaml` et
   propose la configuration toute faite (Docker, disque persistant, variables).
2. **Vérifier le plan.** Le fichier demande le plan **Starter (~7 $/mois)**.
   Ce n'est pas un confort : c'est le premier plan qui donne droit à un
   **disque persistant**. Sur le plan gratuit, le disque est effacé à chaque
   redéploiement — comptes, mots de passe, historique de connexions, journaux
   et offres déposées seraient perdus à chaque mise à jour du code.
3. **Déployer.** Le premier build compile le frontend puis installe le
   backend (~3 min). Render vérifie ensuite `/api/health`.

Aucune variable n'est à saisir à la main : `render.yaml` génère `SECRET_KEY`
et place la base, les fichiers déposés et la clé de session sur le disque
persistant monté dans `/var/data`.

## 2. Brancher le sous-domaine ADOC

1. Dans Render : *Settings* → *Custom Domain* → ajouter
   `veille.adoc-consulting.com`. Render affiche une cible du type
   `xxx.onrender.com`.
2. Dans le DNS Hostinger du domaine `adoc-consulting.com`, ajouter un
   enregistrement **CNAME** : nom `veille`, valeur = la cible fournie.
3. Le certificat HTTPS est émis automatiquement par Render une fois le DNS
   propagé (quelques minutes à quelques heures).

## 3. Premier démarrage : les comptes

Au tout premier lancement sur une base vide, cinq comptes sont créés
automatiquement avec des **mots de passe temporaires** (`admin` / `admin123`,
`assistante` / `assistante123`, `selection` / `selection123`,
`superviseur` / `superviseur123`, `montage` / `montage123`).

Chacun est marqué « doit changer son mot de passe » : à la première connexion,
l'application impose le changement avant tout accès. **Connectez-vous en
`admin` en premier** et changez le mot de passe avant de distribuer les accès
aux autres. L'administrateur peut ensuite créer, renommer ou désactiver des
comptes depuis l'écran *Administration*.

## 4. Ce qui est enregistré

Tout est en base, rien n'est perdu au redémarrage :

| Donnée | Où | Consultable par |
|---|---|---|
| Comptes, rôles, mots de passe hachés (PBKDF2) | table `users` | admin (écran *Administration*) |
| Date et heure de dernière connexion | `users.last_login_at` | admin |
| Chaque connexion et déconnexion | table `activity_logs` | admin (*Journal d'activité*) |
| Changements de mot de passe, avis retenus/écartés, dépôts de fichiers, collectes | table `activity_logs` | admin |
| Photos de journaux, offres technique et financière | `/var/data/uploads` | selon le rôle |

Les sessions durent 12 heures (`TOKEN_TTL_SECONDS`), puis la reconnexion est
demandée.

## 5. Sauvegardes

Render sauvegarde le disque, mais une copie hors hébergeur reste prudente.
Depuis le *Shell* du service :

```bash
sqlite3 /var/data/tenders.db ".backup '/tmp/sauvegarde.db'"
```

puis récupérer le fichier. À faire au moins une fois par mois, ou avant toute
mise à jour importante.

## 6. Mettre à jour l'application

`autoDeploy` est activé : un `git push` sur la branche principale redéclenche
le build et le déploiement. La base et les fichiers déposés, qui vivent sur le
disque persistant, ne sont pas touchés.

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
