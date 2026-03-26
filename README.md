# Pipeline de Données Énergétiques — France

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
ETL (Transformation + Fusion)
    │
    ▼
Entrepôt de données (data/warehouse/)
    │
    ├── PostgreSQL (energy_db)
    │       ├── energy.consumption      → Consommation par région
    │       ├── energy.weather          → Météo horaire
    │       ├── energy.rte_generation   → Mix de génération
    │       └── energy.quality_reports  → Rapports qualité
    │
    ├── MinIO (stockage objet S3)   → Fichiers bruts
    ├── Grafana                     → Tableaux de bord
    └── Prometheus                  → Monitoring du pipeline
```

---

## Stack technique

| Couche | Technologie |
|---|---|
| Orchestration | Apache Airflow 2.7.3 |
| Stockage relationnel | PostgreSQL 13 + pgvector |
| Stockage objet | MinIO (compatible S3) |
| Visualisation | Grafana 10.2.3 |
| Supervision | Prometheus 2.48 |
| Automatisation | n8n |
| Conteneurisation | Docker + Docker Compose |
| Langage | Python 3.8+ |
| Analyse | pandas, scikit-learn, statsmodels, prophet |

---

## Phases du projet

### Phase 1 — Ingestion des données

**Objectif :** Mettre en place les sources de données et le Data Lake.

**Réalisations :**

- Création du client `ODREClient` pour récupérer les données de consommation depuis l'API ODRE (Open Data Réseaux Énergies)
- Implémentation du client `MeteoClient` pour les données météo historiques via Open-Meteo (gratuit, sans clé API)
- Mise en place du `WebScraper` pour le scraping de la plateforme RTE éCO2mix
- Classe `DataSaver` pour sauvegarder les données en JSON et CSV avec horodatage automatique
- Script principal `scripts/ingest.py` pour orchestrer toutes les ingestions

**Structure du Data Lake :**
```
data/
├── raw/api/        → données brutes ODRE
├── raw/meteo/      → données météo
├── raw/scraping/   → données scraping RTE
└── raw/rte/        → données génération RTE
```

**Données collectées :**
- 500 enregistrements de consommation énergétique Île-de-France
- Données météo horaires : température, humidité, vent, précipitations, pression
- Fréquence de collecte : quotidienne

---

### Phase 2 — Transformation ETL & Entrepôt de données

**Objectif :** Transformer les données brutes et construire l'entrepôt analytique.

**Réalisations :**

- `Transformer` : pipeline de nettoyage en chaîne (renommage colonnes → conversion datetime → valeurs manquantes → enrichissement temporel → métriques dérivées → validation)
- Enrichissement temporel automatique : `année`, `mois`, `jour`, `heure`, `jour_semaine`, `est_weekend`, `trimestre`
- `DataMerger` : fusion énergie + météo par jointure temporelle (`merge_asof` avec tolérance de 1 heure)
- Catégories météo dérivées : catégorie de température, catégorie de vent, indicateur de pluie, écart thermique
- Script ETL complet `scripts/run_etl.py` avec sauvegarde `latest.csv` dans l'entrepôt
- Tableau de bord HTML interactif avec Plotly (`scripts/run_dashboard.py`)

---

### Phase 3 — Base de données PostgreSQL

**Objectif :** Charger les données dans PostgreSQL pour les requêtes SQL et les tableaux de bord Grafana.

**Réalisations :**

- Schéma `energy` avec les tables suivantes :
  - `energy.consumption` — consommation avec colonnes temporelles enrichies
  - `energy.weather` — météo horaire
  - `energy.rte_generation` — mix de génération électrique (nucléaire, hydro, éolien, solaire, thermique)
  - `energy.quality_reports` — rapports de gouvernance des données
  - `energy.lineage` — lignage des données
- Vue `energy.consumption_weather` — jointure croisée énergie × météo
- Script `scripts/load_to_db.py` avec gestion de la vue (suppression → chargement → recréation)
- Index optimisés sur `datetime`, `date`, `region`

---

### Phase 4 — Gouvernance & Qualité des données

**Objectif :** Mesurer et suivre la qualité des données du pipeline.

**Réalisations :**

- `DataQualityChecker` : vérification de la complétude, des types, des doublons et des plages de valeurs
- Score de qualité en pourcentage (0 à 100 %)
- Rapports JSON sauvegardés dans `data/governance/quality/`
- Chargement des rapports dans la table `energy.quality_reports`
- Script dédié `scripts/run_governance.py`

---

### Phase 5 — Infrastructure Docker & Supervision

**Objectif :** Conteneuriser l'ensemble du projet et mettre en place la supervision.

**Réalisations :**

- Fichier `docker-compose.yaml` complet incluant :
  - PostgreSQL (port 5433)
  - Airflow (Webserver + Scheduler + Init)
  - MinIO avec création automatique des buckets
  - Grafana (port 3000)
  - Prometheus (port 9090) + PostgreSQL Exporter
  - n8n pour l'automatisation
- Upload des fichiers vers MinIO via `scripts/upload_to_minio.py`
- Tableau de bord Grafana `energy_overview.json` comprenant :
  - Courbe de consommation électrique (série temporelle)
  - Température vs Consommation (double axe)
  - Profil horaire moyen (graphique à barres)
  - Statistiques clés (total, moyenne, pic, minimum)
  - Conditions météo
  - Jauge du score qualité

---

### Phase 6 — Orchestration Airflow Multi-Sources & Multi-Régions

**Objectif :** Industrialiser le pipeline avec Airflow et étendre la couverture à plusieurs régions et sources de données.

**Réalisations :**

**Nouveaux clients de données :**

- `RTEClient` — récupère le mix de génération depuis l'API RTE (nucléaire, hydro, éolien, solaire, thermique)
- `MeteoFranceClient` — données météo régionales via Météo-Concept
- `ODREClient` étendu — support multi-régions avec méthode `for_region()`
- `MeteoClient` étendu — paramètre `region` utilisant les coordonnées configurées

**Régions configurées (`config/settings.py`) :**
```python
REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]
REGION_COORDINATES = {
    "idf":                (48.8566,  2.3522),
    "provence":           (43.5,     5.5),
    "bretagne":           (48.1,    -3.3),
    "nouvelle-aquitaine": (46.0,    -0.5),
}
```

**DAG Airflow `energy_pipeline_multi_sources` :**
```
ingest_energy_group (TaskGroup dynamique)
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

- Callback d'erreur (`on_failure_callback`) pour journalisation
- Planification quotidienne à 6h UTC
- `catchup=False` pour éviter les exécutions rétroactives

---

### Phase 7 — Monitoring Prometheus & Analyse Data Science

**Objectif :** Supervision opérationnelle du pipeline et analyse prédictive de la consommation.

**Métriques Prometheus (`src/monitoring/prometheus_exporter.py`) :**

| Métrique | Type | Description |
|---|---|---|
| `pipeline_duration_seconds` | Histogramme | Durée d'exécution du pipeline |
| `ingested_rows_total` | Compteur | Lignes ingérées par source et région |
| `data_quality_score` | Jauge | Score qualité par jeu de données |
| `task_failures_total` | Compteur | Nombre d'erreurs par tâche |
| `data_freshness_seconds` | Jauge | Âge des données par source |
| `pipeline_runs_total` | Compteur | Exécutions (succès / échec) |

**Tableau de bord Grafana `pipeline_metrics.json` :**
- Durée d'exécution du pipeline dans le temps
- Volume ingéré par source de données
- Taux de succès sur 7 jours glissants
- Fraîcheur des données par source
- Comparaison de consommation entre régions
- Impact du mix de génération (nucléaire, éolien, solaire)

**Modules d'analyse (`src/analysis/`) :**

- `CorrelationAnalyzer` :
  - Corrélation de Pearson entre température et consommation (globale + par mois)
  - Impact de l'humidité et du vent
  - Profil horaire moyen (heures 0 à 23)
  - Comparaison régionale (moyenne, minimum, maximum, écart-type)

- `ConsumptionClustering` :
  - Segmentation des régions par profil de consommation (K-means)
  - Variables : consommation moyenne/écart-type, ratio jour/nuit, heure de pic, saisonnalité
  - Courbe d'inertie (méthode du coude) pour déterminer le nombre optimal de clusters

- `ConsumptionForecaster` :
  - Modèle ARIMA(1,1,1) via statsmodels
  - Modèle Facebook Prophet avec saisonnalités multiples (horaire, hebdomadaire, annuelle)
  - Prévision à 7 jours avec intervalles de confiance à 95 %
  - Indicateurs de performance : MAE, RMSE, MAPE, R²

- Script `scripts/run_analysis.py` : génère un rapport HTML complet avec l'ensemble des résultats

---

## Structure du projet

```
Data_CL/
├── airflow/
│   └── dags/
│       └── energy_pipeline_dag.py     # DAG principal Airflow
├── config/
│   └── settings.py                    # Configuration centralisée
├── data/
│   ├── raw/                           # Data Lake (ignoré par git)
│   ├── processed/                     # Données intermédiaires
│   ├── warehouse/                     # Données prêtes à l'analyse
│   └── governance/                    # Rapports qualité
├── db/
│   └── init/
│       └── 01_create_databases.sql    # Schéma PostgreSQL
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       ├── provisioning/
│       └── dashboards/
│           ├── energy_overview.json   # Tableau de bord énergie × météo
│           └── pipeline_metrics.json  # Tableau de bord supervision
├── scripts/
│   ├── ingest.py                      # Ingestion multi-sources
│   ├── run_etl.py                     # Transformation ETL
│   ├── load_to_db.py                  # Chargement PostgreSQL
│   ├── run_governance.py              # Qualité des données
│   ├── run_dashboard.py              # Tableau de bord HTML
│   └── run_analysis.py               # Analyse complète
└── src/
    ├── ingestion/
    │   ├── api_client.py              # Client HTTP de base (retry, timeout)
    │   ├── odre_client.py             # ODRE — énergie multi-régions
    │   ├── meteo_client.py            # Open-Meteo — météo historique
    │   ├── rte_client.py              # RTE — mix de génération
    │   ├── meteo_france_client.py     # Météo-Concept — météo régionale
    │   ├── web_scraper.py             # Scraping RTE éCO2mix
    │   └── data_saver.py              # Sauvegarde Data Lake
    ├── etl/
    │   ├── transformer.py             # Nettoyage et enrichissement
    │   └── merger.py                  # Fusion énergie × météo × RTE
    ├── governance/
    │   └── quality.py                 # Contrôle qualité des données
    ├── monitoring/
    │   └── prometheus_exporter.py     # Export des métriques Prometheus
    ├── analysis/
    │   ├── correlation_analysis.py    # Corrélation température × consommation
    │   ├── clustering.py              # Clustering K-means régional
    │   └── forecasting.py             # Prévision ARIMA + Prophet
    └── utils/
        └── logger.py                  # Journalisation centralisée
```

---

## Démarrage rapide

### Prérequis
- Docker et Docker Compose installés
- Python 3.8 ou supérieur

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

# Transformation ETL
python scripts/run_etl.py

# Chargement dans PostgreSQL
python scripts/load_to_db.py

# Contrôle qualité
python scripts/run_governance.py

# Analyse complète (corrélation + clustering + prévisions)
python scripts/run_analysis.py
```

### Connexion à PostgreSQL (DBeaver / psql)

```
Hôte     : localhost
Port     : 5433
Base     : energy_db
Utilisateur : airflow
Mot de passe : airflow
```

---

## Variables d'environnement

| Variable | Description | Valeur par défaut |
|---|---|---|
| `DATABASE_URL` | URL de connexion PostgreSQL | `postgresql://airflow:airflow@postgres:5432/energy_db` |
| `RTE_API_KEY` | Clé API RTE | — |
| `METEO_FRANCE_API_KEY` | Clé API Météo-Concept | — |
| `PROMETHEUS_EXPORTER_PORT` | Port de l'exporter Prometheus | `9091` |

---

## Branches

| Branche | Description |
|---|---|
| `main` | Version stable — Phases 1 à 5 |
| `develop` | Dernières fonctionnalités — Phases 6 et 7 |
