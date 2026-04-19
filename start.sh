#!/usr/bin/env sh
# PORT = variable injectée par Railway au runtime (souvent 8080).
set -e
PORT="${PORT:-8000}"

# Railpack / Nixpacks : préférer python3 ou le venv si présent.
if [ -x "/opt/venv/bin/python" ]; then
  PY="/opt/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "[clockify-report] ERREUR : aucun interprète Python trouvé dans PATH." >&2
  exit 1
fi

echo "[clockify-report] Démarrage : ${PY} -m uvicorn — host 0.0.0.0 — port ${PORT}"
exec "$PY" -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
