# Pipeline de Données Énergétiques — France

> Pipeline de données complet pour l'analyse de la consommation d'électricité en France, croisant données énergétiques, météorologiques et de génération. Orchestré avec Airflow, stocké dans PostgreSQL, visualisé avec Grafana et analysé avec des modèles de machine learning.

---

## Résumé 
- Ce que fait ce projet et comment l'expliquer

Ce projet est un **pipeline de données de bout en bout** sur la consommation d'électricité en France. Voici ce qui a été fait, source par source, étape par étape.

---

### Sources de données utilisées

#### 1. API ODRE - Consommation énergétique régionale
- **Site :** https://odre.opendatasoft.com
- **Jeu de données :** `consommation-quotidienne-brute-regionale`
- **Comment :** L'API est publique et gratuite. Elle expose les données via des requêtes HTTP GET avec des paramètres de filtrage (région, limite, tri). On filtre par région (`Île-de-France`, `Provence-Alpes-Côte d'Azur`, etc.) et on pagine les résultats par lots de 100 enregistrements.
- **Ce qu'on récupère :** Consommation brute d'électricité et de gaz par région, par demi-heure, depuis plusieurs mois.
- **Script :** `src/ingestion/odre_client.py` → `scripts/ingest.py`

#### 2. API Open-Meteo — Données météo historiques
- **Site :** https://archive-api.open-meteo.com
- **Comment :** API gratuite, sans clé d'accès. On envoie les coordonnées GPS d'une ville (latitude/longitude) et une plage de dates. L'API retourne des données horaires.
- **Ce qu'on récupère :** Température à 2m, température ressentie, humidité relative, vitesse du vent à 10m, précipitations, couverture nuageuse, pression atmosphérique.
- **Régions couvertes :** Paris (IDF), Aix-en-Provence, Rennes, Bordeaux — avec leurs coordonnées GPS configurées dans `config/settings.py`.
- **Script :** `src/ingestion/meteo_client.py` → `scripts/ingest.py`

#### 3. Scraping RTE éCO2mix
- **Site scrapé :** https://www.rte-france.com/eco2mix/les-donnees-regionales
- **Comment :** On utilise `requests` + `BeautifulSoup` pour récupérer le contenu HTML de la page. On extrait les tableaux de données et les liens de téléchargement disponibles sur la page.
- **Ce qu'on récupère :** Structure de la page, tableaux HTML, liens vers les fichiers téléchargeables de données régionales.
- **Script :** `src/ingestion/web_scraper.py` → `scripts/ingest.py`

#### 4. API RTE — Mix de génération électrique
- **Site :** https://data.rte-france.com
- **Comment :** API officielle de RTE (Réseau de Transport d'Électricité). Nécessite une clé API (variable d'environnement `RTE_API_KEY`). On interroge le dataset `generation-par-filiere` pour obtenir la répartition de la production électrique nationale.
- **Ce qu'on récupère :** Production par filière — nucléaire, hydraulique, éolien, solaire, thermique, autres.
- **Script :** `src/ingestion/rte_client.py` → `scripts/ingest.py`

#### 5. API Météo-Concept — Météo régionale (optionnel)
- **Site :** https://api.meteo-concept.com
- **Comment :** API payante avec clé (variable `METEO_FRANCE_API_KEY`). Offre des données météo plus précises par région française. Utilisée en complément d'Open-Meteo pour les analyses régionales avancées.
- **Script :** `src/ingestion/meteo_france_client.py` → `scripts/ingest.py`

---

### Comment les données sont traitées

#### Étape 1 — Ingestion (`scripts/ingest.py`)
On appelle chaque source de données et on sauvegarde les résultats bruts dans le **Data Lake local** (`data/raw/`), en JSON et CSV, avec un horodatage dans le nom du fichier. Chaque client hérite d'une classe de base `APIClient` qui gère automatiquement les erreurs, les timeouts et les tentatives de reconnexion (3 essais avec délai croissant).

#### Étape 2 — Transformation ETL (`scripts/run_etl.py`)
Le script ETL charge les fichiers bruts et applique une chaîne de transformations :
1. **Renommage** des colonnes vers un schéma normalisé
2. **Conversion** de la colonne `datetime` en format UTC
3. **Gestion des valeurs manquantes** (remplacement par zéro pour les colonnes numériques)
4. **Enrichissement temporel** : ajout de `heure`, `jour_semaine`, `est_weekend`, `trimestre`
5. **Calcul de métriques** : consommation totale, ratio électricité/total, variation horaire
6. **Fusion énergie × météo** par jointure temporelle (`merge_asof`) — on associe chaque mesure énergétique à la mesure météo la plus proche dans le temps (tolérance : 1 heure)
7. **Validation** : suppression des doublons, détection des colonnes avec trop de valeurs nulles
8. Sauvegarde du résultat dans `data/warehouse/energy_consumption_idf/latest.csv`

#### Étape 3 — Chargement en base (`scripts/load_to_db.py`)
Les données transformées sont chargées dans PostgreSQL (base `energy_db`, schéma `energy`) :
- Table `consumption` : données énergétiques par région
- Table `weather` : météo horaire
- Table `rte_generation` : mix de génération
- Vue SQL `consumption_weather` : jointure croisée prête pour Grafana

#### Étape 4 — Gouvernance (`scripts/run_governance.py`)
On mesure la qualité des données avec un score de 0 à 100 % basé sur :
- Complétude des colonnes clés
- Absence de doublons
- Cohérence des plages de valeurs
- Résultat sauvegardé en JSON et chargé dans `energy.quality_reports`

#### Étape 5 — Analyse (`scripts/run_analysis.py`)
Trois analyses sont lancées :
- **Corrélation** : mesure le lien entre température et consommation (coefficient de Pearson)
- **Clustering** : regroupe les régions selon leur profil de consommation avec l'algorithme K-means
- **Prévision** : prédit la consommation des 7 prochains jours avec ARIMA et Prophet
- Un rapport HTML est généré avec tous les résultats

---

### Comment tout est orchestré

Le DAG Airflow `energy_pipeline_multi_sources` (planifié tous les jours à 6h UTC) exécute automatiquement toutes ces étapes dans le bon ordre :

```
[Ingestion ODRE × 4 régions] ──┐
[Ingestion Météo Open-Meteo]   ├──→ ETL → Chargement DB → Dashboard
[Ingestion RTE génération]  ───┘                       → Gouvernance
```

Chaque étape est une tâche Airflow indépendante. Les ingestions s'exécutent en parallèle pour gagner du temps, puis l'ETL attend que toutes soient terminées avant de démarrer.

---

### Ce qu'on peut voir dans Grafana

Une fois les données chargées, deux tableaux de bord sont disponibles :

1. **Énergie × Météo** (`energy_overview`) : courbe de consommation, corrélation température/consommation, profil horaire moyen, score qualité
2. **Supervision du pipeline** (`pipeline_metrics`) : durée d'exécution, volume ingéré, taux de succès, fraîcheur des données

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
