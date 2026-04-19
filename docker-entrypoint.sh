#!/bin/sh
# Ne pas utiliser de valeur par défaut trop basse : Railway envoie souvent PORT=8080.
set -e
PORT="${PORT:-8080}"
echo "[clockify-report] entrypoint PWD=$(pwd) PORT=${PORT} python=$(command -v python || true)"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
