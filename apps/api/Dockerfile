FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
# Les outils d'exploitation voyagent avec l'application : import de vetements,
# nettoyage des medias expires, audit de bout en bout. Sans eux dans l'image,
# ces operations sont impossibles sur un serveur.
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 mirror \
 && mkdir -p /srv/api/var/storage /srv/api/var/garments \
 && chown -R mirror:mirror /srv/api
USER mirror

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
