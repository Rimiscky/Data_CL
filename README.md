# Pipeline de Données Énergétiques — France

> Pipeline de données de bout en bout sur la consommation d'électricité en France : ingestion multi-sources, ETL, gouvernance des données, et tableau de bord HTML interactif déployé automatiquement sur AWS EC2.

**Tableau de bord en production :** http://13.39.99.56:8080

---

## Ce que fait ce projet

Ce projet collecte, transforme et visualise les données d'énergie et de météo en France. Le pipeline s'exécute automatiquement chaque jour et publie un tableau de bord mis à jour sur un serveur AWS EC2.

---

## Sources de données

### 1. API ODRE — Consommation énergétique régionale
- **Site :** https://odre.opendatasoft.com
- **Dataset :** `consommation-quotidienne-brute-regionale`
- **Accès :** Public, gratuit, sans clé API
- **Ce qu'on récupère :** Consommation brute d'électricité et de gaz par région (Île-de-France, Provence-Alpes-Côte d'Azur, Bretagne, Nouvelle-Aquitaine), par demi-heure
- **Script :** `src/ingestion/odre_client.py`

### 2. API Open-Meteo — Météo historique
- **Site :** https://archive-api.open-meteo.com
- **Accès :** Gratuit, sans clé API
- **Ce qu'on récupère :** Température, humidité, vitesse du vent, précipitations, couverture nuageuse, pression — données horaires par coordonnées GPS
- **Régions :** Paris, Aix-en-Provence, Rennes, Bordeaux
- **Script :** `src/ingestion/meteo_client.py`

### 3. API RTE — Mix de génération électrique (OAuth2)
- **Site :** https://digital.iservices.rte-france.com
- **Accès :** Compte RTE requis — token OAuth2 Base64 (`client_id:client_secret`)
- **Ce qu'on récupère :** Production par filière — nucléaire, hydraulique, éolien, solaire, thermique, etc.
- **Authentification :** Flow `client_credentials` → access token Bearer renouvelé automatiquement
- **Variable d'environnement :** `RTE_API_KEY` (token Base64)
- **Script :** `src/ingestion/rte_client.py`

---

## Pipeline de traitement

### Étape 1 — Ingestion (`scripts/ingest.py`)
Appel de chaque source de données, sauvegarde des résultats bruts dans le Data Lake local (`data/raw/`) en JSON et CSV avec horodatage. Chaque client hérite d'un `APIClient` de base qui gère les timeouts, les retries (3 essais) et la journalisation.

### Étape 2 — ETL (`scripts/run_etl.py`)
Transformation en chaîne :
1. Renommage des colonnes vers un schéma normalisé
2. Conversion de `datetime` en UTC
3. Gestion des valeurs manquantes (remplacement par zéro)
4. Enrichissement temporel : `heure`, `jour_semaine`, `est_weekend`, `trimestre`
5. Métriques dérivées : consommation totale, ratio électricité/total, variation horaire
6. Fusion énergie × météo par jointure temporelle (`merge_asof`, tolérance 1 heure)
7. Sauvegarde dans `data/warehouse/energy_consumption_idf/latest.csv`

### Étape 3 — Tableau de bord (`scripts/run_dashboard.py`)
Génération d'un tableau de bord HTML interactif avec Plotly (`output/dashboards/dashboard_energy_idf.html`), puis publication automatique vers le serveur HTTP EC2.

### Étape 4 — Gouvernance (`scripts/run_governance.py`)
Score de qualité (0–100 %) basé sur la complétude, l'absence de doublons et la cohérence des plages de valeurs. Résultats sauvegardés en JSON dans `data/governance/quality/`.

### Étape 5 — Chargement PostgreSQL (`scripts/load_to_db.py`)
Chargement dans la base `energy_db` (schéma `energy`) :
- `energy.consumption` — consommation par région
- `energy.weather` — météo horaire
- `energy.rte_generation` — mix de génération
- `energy.quality_reports` — rapports gouvernance
- Vue `energy.consumption_weather` — jointure croisée prête pour Grafana

---

## Orchestration

Le DAG Airflow `energy_pipeline_multi_sources` s'exécute tous les jours à 6h UTC :

```
[ingest_odre_idf          ]──┐
[ingest_odre_provence      ]  │
[ingest_odre_bretagne      ]  ├──→ run_etl ──→ load_to_postgres ──→ generate_dashboard ──→ publish_dashboards ──→ cleanup_old_files
[ingest_odre_nouvelle-aq.  ]  │                                  └──→ run_governance   ──┘
[ingest_meteo_open_meteo   ]──┤
[ingest_rte_generation     ]──┘
```

- Ingestions en parallèle pour accélérer l'exécution
- Alerte e-mail automatique en cas d'échec (SMTP Gmail)
- Nettoyage automatique des fichiers anciens : raw 7 jours, warehouse 30 jours, logs 14 jours

---

## Déploiement (CI/CD)

### CI — GitHub Actions (`ci.yml`)
À chaque pull request : lint (ruff), tests unitaires, vérification des imports.

### CD — GitHub Actions (`cd.yml`)
À chaque merge sur `main` :
1. Build de l'image Docker et push vers GitHub Container Registry (`ghcr.io/rimiscky/data_cl`)
2. Déploiement automatique sur EC2 via un **runner self-hosted** installé sur l'instance
3. Lancement du conteneur avec le pipeline complet
4. Redémarrage du serveur HTTP sur le port 8080

```
git push → CI (lint + tests) → Build Docker → Push GHCR → Deploy EC2 → Dashboard mis à jour
```

---

## Architecture

```
Sources de données
    ├── API ODRE         → Consommation régionale (énergie)
    ├── API RTE (OAuth2) → Mix de génération (nucléaire, éolien, solaire...)
    └── Open-Meteo       → Météo historique multi-régions
    │
    ▼
Data Lake local (data/raw/)
    │
    ▼
ETL (Transformation + Fusion énergie × météo)
    │
    ▼
Entrepôt (data/warehouse/)
    │
    ├── PostgreSQL (energy_db)
    │       ├── energy.consumption
    │       ├── energy.weather
    │       ├── energy.rte_generation
    │       └── energy.quality_reports
    │
    ├── Dashboard HTML (Plotly) → http://13.39.99.56:8080
    ├── Grafana                 → Tableaux de bord SQL
    └── MinIO (S3)              → Stockage objet
```

---

## Stack technique

| Couche | Technologie |
|---|---|
| Orchestration | Apache Airflow 2.7 |
| Stockage relationnel | PostgreSQL 13 |
| Stockage objet | MinIO (compatible S3) |
| Visualisation | Plotly (HTML) + Grafana 10 |
| Supervision | Prometheus 2.48 |
| Conteneurisation | Docker + Docker Compose |
| CI/CD | GitHub Actions + runner self-hosted EC2 |
| Registry | GitHub Container Registry (GHCR) |
| Langage | Python 3.11 |
| Analyse | pandas, scikit-learn, statsmodels, prophet |

---

## Structure du projet

```
Data_CL/
├── airflow/
│   └── dags/
│       └── energy_pipeline_dag.py     # DAG Airflow principal
├── config/
│   └── settings.py                    # Configuration centralisée
├── data/
│   ├── raw/                           # Data Lake (ignoré par git)
│   │   ├── api/                       # Données brutes ODRE
│   │   ├── meteo/                     # Données météo
│   │   └── rte/                       # Données génération RTE
│   ├── warehouse/                     # Données prêtes à l'analyse
│   └── governance/                    # Rapports qualité
├── db/
│   └── init/
│       └── 01_create_databases.sql    # Schéma PostgreSQL
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/dashboards/
├── output/
│   └── dashboards/                    # Tableaux de bord HTML publiés
├── scripts/
│   ├── ingest.py                      # Ingestion multi-sources
│   ├── run_etl.py                     # Transformation ETL
│   ├── load_to_db.py                  # Chargement PostgreSQL
│   ├── run_governance.py              # Qualité des données
│   ├── run_dashboard.py               # Génération tableau de bord HTML
│   └── run_full_pipeline.py           # Entrypoint Docker (ingestion → ETL → dashboard)
└── src/
    ├── ingestion/
    │   ├── api_client.py              # Client HTTP de base (retry, timeout)
    │   ├── odre_client.py             # ODRE — énergie multi-régions
    │   ├── meteo_client.py            # Open-Meteo — météo historique
    │   ├── rte_client.py              # RTE — mix de génération (OAuth2)
    │   └── data_saver.py              # Sauvegarde Data Lake
    ├── etl/
    │   ├── transformer.py             # Nettoyage et enrichissement
    │   └── merger.py                  # Fusion énergie × météo
    ├── governance/
    │   ├── quality.py                 # Contrôle qualité
    │   ├── catalog.py                 # Catalogue de données
    │   └── lineage.py                 # Lignage des données
    ├── monitoring/
    │   └── prometheus_exporter.py     # Export métriques Prometheus
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
- Docker et Docker Compose
- Python 3.11+

### Lancer l'infrastructure locale

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
| Dashboard EC2 | http://13.39.99.56:8080 | — |

### Exécution manuelle

```bash
# Pipeline complet
python scripts/run_full_pipeline.py

# Étapes individuelles
python scripts/ingest.py
python scripts/run_etl.py
python scripts/load_to_db.py
python scripts/run_governance.py
python scripts/run_dashboard.py
```

### Connexion PostgreSQL

```
Hôte        : localhost
Port        : 5433
Base        : energy_db
Utilisateur : airflow
Mot de passe: airflow
```

---

## Variables d'environnement

| Variable | Description |
|---|---|
| `RTE_API_KEY` | Token OAuth2 Base64 RTE (`client_id:client_secret` encodé en base64) |
| `AIRFLOW_SMTP_PASSWORD` | App Password Gmail pour les alertes e-mail |
| `DATABASE_URL` | URL PostgreSQL (défaut : `postgresql://airflow:airflow@postgres:5432/energy_db`) |

Les secrets de production sont stockés dans **GitHub Actions Secrets** et injectés automatiquement lors du déploiement CD.

---

## Régions configurées

```python
REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]
REGION_COORDINATES = {
    "idf":                (48.8566,  2.3522),  # Paris
    "provence":           (43.5,     5.5),     # Aix-en-Provence
    "bretagne":           (48.1,    -3.3),     # Rennes
    "nouvelle-aquitaine": (46.0,    -0.5),     # Bordeaux
}
```
