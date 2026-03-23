# ============================================================
#  Data Pipeline — Consommation Énergétique Île-de-France
#  Multi-stage build : test → production
# ============================================================

# ── Stage 1 : Base commune ─────────────────────────────────
FROM python:3.12-slim AS base

LABEL maintainer="sambalarimiscky"
LABEL project="energy-pipeline-idf"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dépendances système pour lxml/beautifulsoup
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2 : Tests ────────────────────────────────────────
FROM base AS test

COPY . .

# Lancer les tests unitaires
RUN python -m pytest tests/ -v --tb=short

# ── Stage 3 : Production ──────────────────────────────────
FROM base AS production

# Copier uniquement le code applicatif (pas les tests)
COPY config/ ./config/
COPY src/ ./src/
COPY scripts/ ./scripts/

# Créer les répertoires de données
RUN mkdir -p data/raw/api data/raw/scraping data/processed data/warehouse logs

# Utilisateur non-root pour la sécurité
RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import src; print('OK')" || exit 1

CMD ["python", "scripts/run_full_pipeline.py"]
