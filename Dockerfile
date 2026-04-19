# Railway injecte PORT au runtime (souvent 8080). Forme shell pour CMD = expansion correcte de $PORT.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# Forme shell (pas JSON) : $PORT est lu au démarrage du conteneur, pas au build.
CMD exec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
