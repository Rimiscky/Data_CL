# ============================================================
#  Makefile — Pipeline Data Énergie IDF
#  Commandes réutilisables pour dev, test, docker, CI/CD
# ============================================================

.PHONY: help install test lint clean docker-build docker-test docker-up \
        ingest etl dashboard pipeline

PYTHON   ?= python
DOCKER   ?= docker
COMPOSE  ?= docker compose

# ── Help ─────────────────────────────────────────────────
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Installation ─────────────────────────────────────────
install: ## Installe les dépendances Python
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install flake8

# ── Tests ────────────────────────────────────────────────
test: ## Lance tous les tests unitaires
	$(PYTHON) -m pytest tests/ -v --tb=short

test-cov: ## Lance les tests avec couverture
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

test-fast: ## Lance les tests sans verbose
	$(PYTHON) -m pytest tests/ -q

# ── Lint ─────────────────────────────────────────────────
lint: ## Vérifie le style du code (flake8)
	flake8 src/ scripts/ --max-line-length=120 --statistics \
		--count --show-source --exclude=__pycache__,*.pyc

# ── Pipeline ─────────────────────────────────────────────
ingest: ## Lance l'ingestion des données
	$(PYTHON) scripts/ingest.py

etl: ## Lance le pipeline ETL
	$(PYTHON) scripts/run_etl.py

dashboard: ## Génère le dashboard
	$(PYTHON) scripts/run_dashboard.py

pipeline: ## Lance le pipeline complet (ingest → ETL → dashboard)
	$(PYTHON) scripts/run_full_pipeline.py

# ── Docker ───────────────────────────────────────────────
docker-build: ## Build toutes les images Docker
	$(COMPOSE) build pipeline-tests pipeline-ingestion pipeline-etl pipeline-dashboard pipeline-full

docker-test: ## Lance les tests dans Docker
	$(DOCKER) run --rm $$($(COMPOSE) images pipeline-tests -q 2>/dev/null || echo data_cl-pipeline-tests) \
		$(PYTHON) -m pytest tests/ -v --tb=short

docker-up: ## Lance le pipeline complet dans Docker
	$(COMPOSE) up pipeline-full

docker-ingest: ## Lance l'ingestion dans Docker
	$(COMPOSE) up pipeline-ingestion

docker-etl: ## Lance l'ETL dans Docker
	$(COMPOSE) up pipeline-etl

docker-dashboard: ## Lance le dashboard dans Docker
	$(COMPOSE) up pipeline-dashboard

docker-down: ## Arrête tous les conteneurs
	$(COMPOSE) down --remove-orphans

# ── Nettoyage ────────────────────────────────────────────
clean: ## Nettoie les fichiers temporaires
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf reports/ .coverage htmlcov/

clean-data: ## Supprime les données générées (attention !)
	@echo "⚠ Suppression des données dans data/ et output/"
	@read -p "Confirmer ? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf data/raw/api/* data/raw/scraping/* data/processed/* data/warehouse/* output/*
