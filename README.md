# Pipeline de Données Énergétiques — France

[![pipeline status](https://gitlab.com/Rimiscky/data_cl/badges/main/pipeline.svg)](https://gitlab.com/Rimiscky/data_cl/-/pipelines)
[![coverage](https://gitlab.com/Rimiscky/data_cl/badges/main/coverage.svg)](https://gitlab.com/Rimiscky/data_cl/-/commits/main)
[![GitLab Release](https://gitlab.com/Rimiscky/data_cl/-/badges/release.svg)](https://gitlab.com/Rimiscky/data_cl/-/releases)

> Pipeline de données de bout en bout sur la consommation d'électricité en France : ingestion multi-sources, ETL, gouvernance des données, tableaux de bord HTML interactifs avec filtres JS et animations, et application Streamlit multi-régions déployée sur AWS EC2.

---

## Ce que fait ce projet

Ce projet collecte, transforme et visualise les données d'énergie et de météo en France. Le pipeline s'exécute automatiquement chaque jour via GitLab CI/CD et génère des tableaux de bord HTML interactifs ainsi qu'une application Streamlit déployée sur AWS EC2.

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

### Étape 3 — Tableaux de bord (`scripts/run_dashboard.py`)
Génération de tableaux de bord HTML interactifs avec Plotly :
- `output/dashboards/dashboard_energy_idf.html` — dashboard régional (9 graphiques, filtres JS client-side)
- `output/dashboards/dashboard_comparaison.html` — comparaison inter-régionale (4 régions, fichier statique)
- `output/dashboards/dashboard_cross_energy_meteo.html` — corrélation énergie × météo
- `output/dashboards/index.html` — page d'accueil des tableaux de bord

### Étape 4 — Gouvernance (`scripts/run_governance.py`)
Score de qualité (0–100 %) basé sur la complétude, l'absence de doublons et la cohérence des plages de valeurs. Résultats sauvegardés en JSON dans `data/governance/quality/`.

### Étape 5 — Chargement PostgreSQL (`scripts/load_to_db.py`)
Chargement dans la base `energy_db` (schéma `energy`) :
- `energy.consumption` — consommation par région
- `energy.weather` — météo horaire
- `energy.rte_generation` — mix de génération
- `energy.quality_reports` — rapports gouvernance

---

## Orchestration

Le DAG Airflow `energy_pipeline_multi_sources` s'exécute tous les jours à 6h UTC :

```
[ingest_odre_idf          ]──┐
[ingest_odre_provence      ]  │
[ingest_odre_bretagne      ]  ├──→ run_etl ──→ load_to_postgres ──→ generate_dashboard ──→ cleanup_old_files
[ingest_odre_nouvelle-aq.  ]  │                                  └──→ run_governance   ──┘
[ingest_meteo_open_meteo   ]──┤
[ingest_rte_generation     ]──┘
```

- Ingestions en parallèle pour accélérer l'exécution
- Alerte e-mail automatique en cas d'échec (SMTP Gmail)
- Nettoyage automatique des fichiers anciens : raw 7 jours, warehouse 30 jours, logs 14 jours

---

## Déploiement (CI/CD)

### CI — GitLab CI (`test` stage)
À chaque push : lint (flake8), tests unitaires Python 3.11 + 3.12, tests Docker.

### CD — GitLab CI (`deploy` stage)
À chaque merge sur `main` (hors `.md` et `docs/`) :
1. Build de l'image Docker
2. Exécution du pipeline complet (ingestion → ETL → gouvernance → dashboards)
3. Génération des tableaux de bord HTML mis à jour

```
git push → CI (lint + tests + docker) → CD (pipeline + dashboards)
```

Les secrets (`RTE_API_KEY`, etc.) sont stockés dans **GitLab CI/CD Variables** (`Settings → CI/CD → Variables`).

---

## Déploiement EC2 (production)

L'instance AWS EC2 (`13.39.99.56`, Ubuntu 22.04) héberge les deux interfaces en production.

### Services déployés

| Service | Port | Démarrage | Script |
|---|---|---|---|
| Dashboards HTML | 8080 | `@reboot` cron | `python3 -m http.server 8080` |
| Application Streamlit | 8501 | systemd `streamlit.service` | `deploy_streamlit_ec2.sh` |

### Déployer les dashboards HTML

```bash
bash scripts/deploy_ec2.sh
```

### Déployer / mettre à jour Streamlit

```bash
bash scripts/deploy_streamlit_ec2.sh
```

### Maintenance disque (automatique)

Un cron tourne chaque **dimanche à 3h UTC** pour libérer le disque :
```bash
# Installation (une seule fois)
bash scripts/setup_cleanup_cron.sh

# Exécution manuelle
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 \
  "PROJECT_DIR=/home/ubuntu sudo -E bash /home/ubuntu/scripts/cleanup_disk.sh"
```

Cibles : images Docker, logs > 14j, `data/raw/` > 7j, cache APT/pip, `/tmp`.

### Variables d'environnement sur EC2

Stockées dans `/home/ubuntu/.env` (chmod 600), injectées dans le service systemd via `EnvironmentFile`.

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
    ├── Dashboards HTML (Plotly)   → EC2 :8080  (filtres JS + animations, 9 graphiques)
    └── Application Streamlit      → EC2 :8501  (6 onglets interactifs, service systemd)
```

---

## Stack technique

| Couche | Technologie |
|---|---|
| Orchestration | Apache Airflow 2.7 |
| Stockage relationnel | PostgreSQL 13 |
| Stockage objet | MinIO (compatible S3) |
| Visualisation interactive | Streamlit 1.x + Plotly |
| Tableaux de bord statiques | HTML/JS/Plotly (client-side filtering) |
| Supervision | Prometheus 2.48 |
| Conteneurisation | Docker + Docker Compose |
| CI/CD | GitLab CI/CD |
| Langage | Python 3.11 |
| Analyse | pandas, scikit-learn, statsmodels, prophet |

---

## Application Streamlit

L'application `app_streamlit.py` offre une interface exploratoire complète, organisée en 6 onglets :

| Onglet | Contenu |
|---|---|
| Vue d'ensemble | KPIs globaux, tendances |
| Consommation | Courbes horaires, heatmap, histogramme |
| Météo × Énergie | Corrélation température/consommation |
| Mix de production | Répartition par filière (nucléaire, éolien, solaire…) |
| Gouvernance | Score qualité, rapports |
| Prévisions | Forecast Prophet + ARIMA |

**Sidebar :** sélecteur de région, période (7j / 30j / 90j), seuil d'alerte consommation, export CSV.

```bash
# Lancer l'application
streamlit run app_streamlit.py
# → http://localhost:8501
```

---

## Tableaux de bord HTML

Quatre fichiers HTML autonomes générés dans `output/dashboards/` :

### `dashboard_energy_idf.html` — Tableau de bord régional
- Données brutes embarquées en JSON (`window.D`)
- Filtres JavaScript client-side : plage de dates, saison, type de jour, tranche horaire
- Bannière explicative si aucune donnée pour le filtre sélectionné
- Animations : compteurs KPI animés (`easeOutCubic`), `fadeInUp` sur les graphiques, shimmer pendant la mise à jour
- **9 graphiques** : série temporelle, profil 24h par saison, profil horaire, jour de semaine, box plots par heure, heatmap jour×heure, heatmap calendrier date×heure, semaine vs weekend, distribution

### `dashboard_comparaison.html` — Comparaison inter-régionale
- Sélection de deux régions à comparer
- Graphiques : séries temporelles, radar, histogrammes
- KPIs animés, badge VS pulsant, bouton de comparaison avec état de chargement

### `dashboard_cross_energy_meteo.html` — Corrélation énergie × météo
- Analyse croisée consommation électrique et données météorologiques
- Corrélations température / humidité / vent × consommation
- Vue multi-régions

### `index.html` — Page d'accueil
- Liens vers les trois dashboards et l'application Streamlit
- Badge ODRE · GitLab CI/CD

```bash
# Servir les dashboards localement
cd output/dashboards && python3 -m http.server 8080
# → http://localhost:8080
```

---

## Structure du projet

```
Data_CL/
├── app_streamlit.py                   # Application Streamlit (6 onglets)
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
│   └── dashboards/                    # Tableaux de bord HTML
│       ├── index.html                 # Page d'accueil (suivi par git)
│       ├── dashboard_energy_idf.html         # Dashboard régional — 9 graphiques (généré)
│       ├── dashboard_comparaison.html        # Comparaison inter-régionale (statique)
│       └── dashboard_cross_energy_meteo.html # Corrélation énergie × météo (généré)
├── scripts/
│   ├── ingest.py                      # Ingestion multi-sources
│   ├── run_etl.py                     # Transformation ETL
│   ├── load_to_db.py                  # Chargement PostgreSQL
│   ├── run_governance.py              # Qualité des données
│   ├── run_dashboard.py               # Génération tableaux de bord HTML
│   ├── run_full_pipeline.py           # Entrypoint pipeline complet
│   ├── deploy_ec2.sh                  # Déploiement dashboards HTML vers EC2
│   ├── deploy_streamlit_ec2.sh        # Déploiement app Streamlit sur EC2 (systemd)
│   ├── cleanup_disk.sh                # Nettoyage disque EC2 (Docker, logs, raw, APT)
│   └── setup_cleanup_cron.sh          # Installation cron nettoyage sur EC2
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
    │   ├── dashboard.py               # Génération HTML (filtres JS + animations)
    │   ├── cross_dashboard.py         # Dashboard corrélation énergie × météo (généré)
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
docker-compose up -d postgres minio prometheus airflow-init
docker-compose up -d airflow-webserver airflow-scheduler
```

### Interfaces disponibles

| Service | URL locale | URL EC2 (production) |
|---|---|---|
| Dashboards HTML | http://localhost:8080 | http://13.39.99.56:8080/dashboards/ |
| Application Streamlit | http://localhost:8501 | http://13.39.99.56:8501 |
| Airflow | http://localhost:8080 | — |
| MinIO | http://localhost:9001 | — |
| Prometheus | http://localhost:9090 | — |

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

# Application Streamlit
streamlit run app_streamlit.py
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

Les secrets de production sont stockés dans **GitLab CI/CD Variables** (`Settings → CI/CD → Variables`) et injectés automatiquement lors du déploiement CD.

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
