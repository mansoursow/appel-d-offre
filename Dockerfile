# ===========================================================================
# Image de production : un seul conteneur qui sert l'API ET l'interface.
# ===========================================================================
# Etape 1 : compilation de l'interface React (Node n'est plus necessaire
# ensuite, seul le dossier `dist` produit est repris dans l'image finale).
FROM node:20-alpine AS frontend

WORKDIR /build
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build


# Etape 2 : l'API FastAPI, qui sert aussi le `dist` produit ci-dessus.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FRONTEND_DIST=/srv/frontend_dist \
    DATABASE_URL=sqlite:////var/data/tenders.db \
    UPLOAD_DIR=/var/data/uploads \
    SECRET_KEY_FILE=/var/data/.secret_key

WORKDIR /srv

COPY app/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/backend/app ./app
COPY --from=frontend /build/dist ./frontend_dist

# /var/data est le point de montage du disque PERSISTANT : la base SQLite, les
# fichiers deposes et la cle de session y survivent aux redeploiements.
RUN mkdir -p /var/data

EXPOSE 8000

# L'hebergeur impose souvent le port via la variable PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
