# Image explicite : le PORT est lu au démarrage du conteneur (variable Railway).
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

# ${PORT} est injecté par Railway au runtime (souvent 8080).
CMD ["sh", "-c", "exec python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
