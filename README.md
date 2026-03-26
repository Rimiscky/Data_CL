# Pipeline de Données Énergétiques — Île-de-France & Multi-Régions

> Pipeline de données complet pour l'analyse de la consommation d'électricité en France, croisant données énergétiques, météorologiques et de génération. Orchestré avec Airflow, stocké dans PostgreSQL, visualisé avec Grafana et analysé avec des modèles de machine learning.

---

## Architecture générale

```
Sources de données
    │
    ├── API ODRE         → Consommation régionale (énergie)
    ├── API RTE          → Mix de génération (nucléaire, éolien, solaire...)
    ├── Open-Meteo       → Données météo historiques (multi-régions)
    └── Météo-Concept    → Données météo régionales (France)
    │
    ▼
Data Lake local (data/raw/)
    │
    ▼
ETL (Transform + Merge)
    │
    ▼
Data Warehouse (data/warehouse/)
    │
    ├── PostgreSQL (energy_db)
    │       ├── energy.consumption   → Consommation par région
    │       ├── energy.weather       → Météo horaire
    │       ├── energy.rte_generation→ Mix de génération
    │       └── energy.quality_reports
    │
    ├── MinIO (S3 local)    → Stockage objet des fichiers bruts
    ├── Grafana             → Dashboards de visualisation
    └── Prometheus          → Monitoring du pipeline
```

---

## Stack technique

| Couche | Technologie |
|---|---|
| Orchestration | Apache Airflow 2.7.3 |
| Stockage relationnel | PostgreSQL 13 + pgvector |
| Stockage objet | MinIO (compatible S3) |
| Visualisation | Grafana 10.2.3 |
| Monitoring | Prometheus 2.48 |
| Automatisation | n8n |
| Conteneurisation | Docker + Docker Compose |
| Langage | Python 3.8+ |
| Analyse | pandas, scikit-learn, statsmodels, prophet |

---

## Phases du projet

### Phase 1 — Ingestion des données (Days 1-2)

**Objectif :** Mettre en place les sources de données et le Data Lake.

**Ce qui a été fait :**

- Création du client API `ODREClient` (hérite de `APIClient`) pour récupérer les données de consommation énergétique depuis l'API ODRE (Open Data Réseaux Énergies)
- Implémentation du client `MeteoClient` pour les données météo historiques via Open-Meteo (gratuit, sans clé API)
- Mise en place du `WebScraper` pour le scraping de RTE éCO2mix
- Classe `DataSaver` pour sauvegarder en JSON et CSV avec horodatage automatique
- Structure du Data Lake :
  ```
  data/
  ├── raw/api/        → données brutes ODRE
  ├── raw/meteo/      → données météo
  ├── raw/scraping/   → données scraping RTE
  └── raw/rte/        → données génération RTE
  ```
- Script `scripts/ingest.py` pour orchestrer toutes les ingestions

**Données collectées :**
- 500 enregistrements de consommation énergétique Île-de-France
- Données météo horaires : température, humidité, vent, précipitations, pression
- Fréquence : quotidienne

---

### Phase 2 — ETL & Warehouse (Days 2-3)

**Objectif :** Transformer les données brutes et construire le warehouse analytique.

**Ce qui a été fait :**

- `Transformer` : pipeline de nettoyage en chaîne (rename → datetime → missing values → enrichissement temporel → métriques dérivées → validation)
- Enrichissement temporel automatique : `year`, `month`, `day`, `hour`, `day_of_week`, `is_weekend`, `quarter`
- `DataMerger` : fusion énergie + météo par jointure temporelle (`merge_asof` avec tolérance 1h)
- Catégories météo dérivées : `temp_category`, `wind_category`, `is_rainy`, `thermal_gap`
- Script ETL complet `scripts/run_etl.py` avec sauvegarde `latest.csv` dans le warehouse
- Dashboard HTML statique avec Plotly (`scripts/run_dashboard.py`)

**Structure warehouse :**
```
data/warehouse/
└── energy_consumption_idf/
    └── latest.csv    → données transformées et fusionnées
```

---

### Phase 3 — Base de données PostgreSQL (Days 3-4)

**Objectif :** Charger les données dans PostgreSQL pour les requêtes SQL et Grafana.

**Ce qui a été fait :**

- Schéma `energy` avec tables :
  - `energy.consumption` — consommation avec colonnes temporelles
  - `energy.weather` — météo horaire
  - `energy.rte_generation` — mix de génération (nucléaire, hydro, éolien, solaire, thermique)
  - `energy.quality_reports` — rapports de gouvernance
  - `energy.lineage` — lignage des données
- Vue `energy.consumption_weather` — jointure croisée énergie × météo
- Script `scripts/load_to_db.py` avec gestion de la vue (drop → load → recreate)
- Indexes optimisés sur `datetime`, `date`, `region`

---

### Phase 4 — Gouvernance & Qualité (Days 3-4)

**Objectif :** Mesurer et suivre la qualité des données.

**Ce qui a été fait :**

- `DataQualityChecker` : vérifie complétude, types, doublons, plages de valeurs
- Score de qualité en pourcentage (0-100%)
- Rapports JSON sauvegardés dans `data/governance/quality/`
- Chargement des rapports dans `energy.quality_reports`
- Script `scripts/run_governance.py`

---

### Phase 5 — Infrastructure Docker & Monitoring (Days 3-4)

**Objectif :** Containeriser l'ensemble du stack et mettre en place le monitoring.

**Ce qui a été fait :**

- `docker-compose.yaml` complet avec :
  - PostgreSQL (port 5433)
  - Airflow Webserver + Scheduler + Init
  - MinIO + init automatique des buckets
  - Grafana (port 3000)
  - Prometheus (port 9090)
  - PostgreSQL Exporter pour Prometheus
  - n8n pour l'automatisation
- Upload des données vers MinIO via `scripts/upload_to_minio.py`
- Dashboard Grafana `energy_overview.json` :
  - Consommation électrique (série temporelle)
  - Température vs Consommation (dual axis)
  - Profil horaire moyen (barchart)
  - Stats clés (total, moyenne, pic, min)
  - Conditions météo
  - Score qualité (jauge)

---

### Phase 6 — Orchestration Airflow Multi-Sources (Days 5-6)

**Objectif :** Industrialiser le pipeline avec Airflow et étendre à plusieurs régions et sources.

**Ce qui a été fait :**

**Nouveaux clients de données :**

- `RTEClient` — récupère le mix de génération depuis l'API RTE (nucléaire, hydro, éolien, solaire, thermique)
- `MeteoFranceClient` — données météo régionales via Météo-Concept (avec clé API)
- Extension `ODREClient` — support multi-régions avec factory method `for_region(region_key)`
- Extension `MeteoClient` — paramètre `region` pour utiliser les coordonnées configurées

**Configuration multi-régions (`config/settings.py`) :**
```python
REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]
REGION_COORDINATES = {
    "idf":                 (48.8566, 2.3522),
    "provence":            (43.5,    5.5),
    "bretagne":            (48.1,   -3.3),
    "nouvelle-aquitaine":  (46.0,   -0.5),
}
```

**DAG Airflow `energy_pipeline_multi_sources` :**
```
ingest_energy_group (TaskGroup)
  ├── ingest_odre_idf
  ├── ingest_odre_provence
  ├── ingest_odre_bretagne
  └── ingest_odre_nouvelle-aquitaine
ingest_meteo_open_meteo
ingest_rte_generation
        │
        ▼
    run_etl
        │
        ▼
  load_to_postgres
        │
    ┌───┴───┐
generate_dashboard  run_governance
```

- `on_failure_callback` pour logging des erreurs
- Planification quotidienne à 6h UTC
- `catchup=False` pour éviter les backfills

---

### Phase 7 — Monitoring Prometheus & Analyse Data Science (Days 6-7)

**Objectif :** Monitoring opérationnel et analyse prédictive.

**Prometheus Exporter (`src/monitoring/prometheus_exporter.py`) :**

| Métrique | Type | Description |
|---|---|---|
| `pipeline_duration_seconds` | Histogram | Durée d'exécution |
| `ingested_rows_total` | Counter | Lignes ingérées par source/région |
| `data_quality_score` | Gauge | Score qualité par dataset |
| `task_failures_total` | Counter | Erreurs par tâche |
| `data_freshness_seconds` | Gauge | Âge des données |
| `pipeline_runs_total` | Counter | Exécutions (success/failed) |

**Dashboard Grafana `pipeline_metrics.json` :**
- Durée d'exécution du pipeline
- Volume ingéré par source
- Taux de succès (7 jours)
- Fraîcheur des données
- Comparaison régionale de consommation
- Impact du mix de génération

**Modules d'analyse (`src/analysis/`) :**

- `CorrelationAnalyzer` :
  - Corrélation de Pearson température ↔ consommation (globale + par mois)
  - Impact humidité, vent, génération RTE
  - Profil horaire moyen (heure 0-23)
  - Comparaison régionale (moyenne, min, max, std)

- `ConsumptionClustering` :
  - K-means sur profils régionaux
  - Features : consommation moyenne/std, ratio jour/nuit, pic horaire, saisonnalité
  - Courbe d'inertie (elbow method) pour choisir k optimal

- `ConsumptionForecaster` :
  - ARIMA(1,1,1) avec statsmodels
  - Facebook Prophet avec saisonnalités multiples (horaire, hebdomadaire, annuelle)
  - Prévision à 7 jours avec intervalles de confiance
  - Évaluation : MAE, RMSE, MAPE, R²

- Script `scripts/run_analysis.py` : rapport HTML complet avec tous les résultats

---

## Structure du projet

```
Data_CL/
├── airflow/
│   └── dags/
│       └── energy_pipeline_dag.py    # DAG principal
├── config/
│   └── settings.py                   # Configuration centralisée
├── data/
│   ├── raw/                          # Data Lake (gitignored)
│   ├── processed/                    # Données intermédiaires
│   ├── warehouse/                    # Données prêtes à l'analyse
│   └── governance/                   # Rapports qualité
├── db/
│   └── init/
│       └── 01_create_databases.sql   # Schéma PostgreSQL
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
│           ├── energy_overview.json  # Dashboard énergie × météo
│           └── pipeline_metrics.json # Dashboard monitoring
├── scripts/
│   ├── ingest.py                     # Ingestion multi-sources
│   ├── run_etl.py                    # ETL
│   ├── load_to_db.py                 # Chargement PostgreSQL
│   ├── run_governance.py             # Qualité des données
│   ├── run_dashboard.py              # Dashboard HTML
│   └── run_analysis.py              # Analyse complète
└── src/
    ├── ingestion/
    │   ├── api_client.py             # Client HTTP de base
    │   ├── odre_client.py            # ODRE (énergie multi-régions)
    │   ├── meteo_client.py           # Open-Meteo (météo)
    │   ├── rte_client.py             # RTE (génération)
    │   ├── meteo_france_client.py    # Météo-Concept
    │   ├── web_scraper.py            # Scraping RTE
    │   └── data_saver.py             # Sauvegarde Data Lake
    ├── etl/
    │   ├── transformer.py            # Nettoyage et enrichissement
    │   └── merger.py                 # Fusion énergie × météo × RTE
    ├── governance/
    │   └── quality.py                # Contrôle qualité
    ├── monitoring/
    │   └── prometheus_exporter.py    # Export métriques
    ├── analysis/
    │   ├── correlation_analysis.py   # Corrélation temp × conso
    │   ├── clustering.py             # Clustering K-means régional
    │   └── forecasting.py            # ARIMA + Prophet
    └── utils/
        └── logger.py                 # Logger centralisé
```

---

## Démarrage rapide

### Prérequis
- Docker & Docker Compose
- Python 3.8+

### Lancement de l'infrastructure

```bash
docker-compose up -d postgres minio grafana prometheus airflow-init
docker-compose up -d airflow-webserver airflow-scheduler
```

### Interfaces disponibles

| Service | URL | Identifiants |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Grafana | http://localhost:3000 | admin / admin |
| MinIO | http://localhost:9001 | admin / password |
| Prometheus | http://localhost:9090 | — |

### Exécution manuelle du pipeline

```bash
# Ingestion des données
python scripts/ingest.py

# ETL
python scripts/run_etl.py

# Chargement PostgreSQL
python scripts/load_to_db.py

# Gouvernance
python scripts/run_governance.py

# Analyse complète (corrélation + clustering + prévisions)
python scripts/run_analysis.py
```

### Connexion PostgreSQL (DBeaver / psql)

```
Host:     localhost
Port:     5433
Database: energy_db
User:     airflow
Password: airflow
```

---

## Variables d'environnement

| Variable | Description | Défaut |
|---|---|---|
| `DATABASE_URL` | URL PostgreSQL | `postgresql://airflow:airflow@postgres:5432/energy_db` |
| `RTE_API_KEY` | Clé API RTE | — |
| `METEO_FRANCE_API_KEY` | Clé API Météo-Concept | — |
| `PROMETHEUS_EXPORTER_PORT` | Port exporter | `9091` |

---

## Branche develop

La branche `develop` contient les dernières fonctionnalités :
- Ingestion multi-régions (IDF, Provence, Bretagne, Nouvelle-Aquitaine)
- Client RTE pour le mix de génération électrique
- DAG Airflow avec TaskGroups dynamiques
- Modules d'analyse : corrélation, clustering, prévision
- Monitoring Prometheus + dashboard Grafana pipeline
