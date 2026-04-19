#!/usr/bin/env sh
# Démarrage au runtime : PORT doit être lu ici, pas figé au build (Railway / Nixpacks).
set -e
PORT="${PORT:-8000}"
echo "[clockify-report] Démarrage uvicorn sur 0.0.0.0 port ${PORT}"
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
