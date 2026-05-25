# Architecture du projet

## Vue d'ensemble

Le projet est un pipeline de données de bout en bout pour la consommation énergétique française. Il collecte des données depuis 3 sources publiques, les transforme, les stocke, et expose plusieurs interfaces de visualisation.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOURCES DE DONNÉES                       │
│                                                                 │
│  API ODRE          API Open-Meteo        API RTE (OAuth2)       │
│  (consommation     (météo historique     (mix génération         │
│   régionale)        horaire, gratuit)     électrique)           │
└──────────┬──────────────────┬───────────────────┬──────────────┘
           │                  │                   │
           ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION (src/ingestion/)                    │
│                                                                 │
│  ODREClient      MeteoClient          RTEClient                 │
│  (4 régions)     (4 villes GPS)       (OAuth2 client_creds)     │
│                                                                 │
│  Retry 3x · Timeout · Logging · Sauvegarde horodatée           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAKE  (data/raw/)                        │
│                                                                 │
│  data/raw/api/       data/raw/meteo/      data/raw/rte/         │
│  odre_conso_*.json   meteo_idf_*.csv      rte_gen_mix_*.json    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ETL (src/etl/)                             │
│                                                                 │
│  Extractor   →   Transformer   →   DataMerger   →   Loader     │
│  (lecture        (normalisation,    (merge_asof     (warehouse  │
│   JSON/CSV)       enrichissement     énergie×météo,  latest.csv │
│                   temporel)          tolérance 1h)   + partitions)
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   WAREHOUSE (data/warehouse/)                    │
│                                                                 │
│  energy_consumption_idf/latest.csv          500 lignes, 24+ col │
│  energy_consumption_provence/latest.csv     500 lignes          │
│  energy_consumption_bretagne/latest.csv     500 lignes          │
│  energy_consumption_nouvelle-aquitaine/     500 lignes          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
               ┌───────────┴───────────────────────┐
               ▼                                   ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│    GOUVERNANCE (src/           │    │    VISUALISATION             │
│    governance/)               │    │                              │
│                               │    │  DashboardBuilder            │
│  DataQualityChecker           │    │  → dashboard_energy_idf.html │
│  (score 0-100%, 7 règles)     │    │    (9 graphiques, filtres JS) │
│  DataLineageTracker           │    │                              │
│  DataCatalog                  │    │  CrossDashboardBuilder       │
│                               │    │  → dashboard_cross_meteo.html│
│  data/governance/             │    │    (6 graphiques énergie×météo│
│  quality/*.json               │    │                              │
│  lineage/*.json               │    │  app_streamlit.py            │
│  catalog/catalog.json         │    │  → :8501 (6 onglets)         │
└──────────────────────────────┘    └──────────────────────────────┘
```

---

## Composants détaillés

### Ingestion (`src/ingestion/`)

| Classe | Source | Authentification | Données |
|---|---|---|---|
| `ODREClient` | odre.opendatasoft.com | Aucune (public) | Conso brute élec+gaz par région/heure |
| `MeteoClient` | archive-api.open-meteo.com | Aucune (gratuit) | Temp, humidité, vent, pluie, nuages |
| `RTEClient` | digital.iservices.rte-france.com | OAuth2 client_credentials | Mix génération par filière |

Tous héritent de `APIClient` (base) qui gère :
- Retry automatique (3 tentatives, backoff exponentiel)
- Timeout configurable
- Logging structuré via `get_logger()`
- Context manager (`__enter__` / `__exit__`)

### ETL (`src/etl/`)

```
Extractor → Transformer → DataMerger → Loader
```

- **Extractor** : lit les fichiers JSON/CSV du Data Lake, retourne un DataFrame
- **Transformer** :
  - Renomme les colonnes vers un schéma normalisé (`elec_consumption_mw`, `gas_consumption_mw`…)
  - Convertit `datetime` en UTC
  - Remplace les NaN par 0 (`fill_zero` strategy)
  - Enrichissement temporel : `year`, `month`, `day`, `hour`, `day_of_week`, `is_weekend`, `quarter`
  - Métriques dérivées : `total_consumption_mw`, `elec_ratio`, `elec_change_mw`, `elec_change_pct`
- **DataMerger** : `merge_asof` énergie × météo sur `datetime` (tolérance 1h), ajoute catégories (`temp_category`, `wind_category`, `is_rainy`, `thermal_gap`)
- **Loader** : sauvegarde `latest.csv` + partitions `year=YYYY/data_<timestamp>.csv`

### Analyse (`src/analysis/`)

- **`DataAnalyzer`** : statistiques descriptives, profils horaires/saisonniers, détection anomalies (z-score σ=2.5)
- **`DashboardBuilder`** : prend un `DataAnalyzer`, génère 9 graphiques Plotly, exporte HTML autonome (données embarquées JSON)
- **`CrossDashboardBuilder`** : prend un DataFrame fusionné (doit contenir `temperature_2m`), génère 6 graphiques corrélation énergie×météo

### Pipeline CI/CD (`.gitlab-ci.yml`)

```
stage: test                     stage: deploy          stage: pipeline
─────────────────               ──────────────         ────────────────
test:py311      ──┐             deploy:ec2             pipeline:manual
test:py312      ──┼──→ docker   (main + src changes)   (déclenchement
lint:flake8     ──┘   :test     self-hosted runner)     manuel, MAX_RECORDS)
```

---

## Flux de données complet

```
1. ODRE API ─────→ data/raw/api/odre_consommation_<region>_<ts>.json
2. Open-Meteo ───→ data/raw/meteo/meteo_idf_<ts>.csv
3. RTE API ──────→ data/raw/rte/rte_generation_mix_<ts>.json
                              │
4. ETL Pipeline ─────────────┘
   Extractor → Transformer → DataMerger(énergie+météo) → Loader
                              │
5. Warehouse ─────────────────┘
   data/warehouse/energy_consumption_<region>/latest.csv
                              │
         ┌────────────────────┴──────────────────────┐
         │                                           │
6a. DashboardBuilder                    6b. CrossDashboardBuilder
    (DataAnalyzer(df))                      (merged_df)
         │                                           │
7a. dashboard_energy_idf.html           7b. dashboard_cross_energy_meteo.html
    (9 charts, filtres JS)                  (6 charts, énergie×météo)
         │                                           │
8. scp → EC2 /home/ubuntu/www/dashboards/ (port 8080)

9. app_streamlit.py ← charge warehouse dynamiquement
   systemd streamlit.service → EC2 port 8501
```

---

## Infrastructure EC2

```
EC2 Ubuntu 22.04 (t2.micro) — 13.39.99.56 — eu-west-3
│
├── port 8080 — Dashboards HTML (python3 -m http.server, cron @reboot)
│   └── /home/ubuntu/www/dashboards/
│
├── port 8501 — Streamlit (systemd streamlit.service, restart on-failure)
│   └── /home/ubuntu/app_streamlit.py
│
├── /home/ubuntu/.env (chmod 600)
│   └── RTE_API_KEY=<token_base64>
│
├── /home/ubuntu/data/ ← warehouse + raw data
│   ├── warehouse/energy_consumption_*/latest.csv
│   └── raw/meteo/ + raw/rte/
│
└── cron — dimanche 3h UTC
    └── cleanup_disk.sh (Docker, logs>14j, raw>7j, APT/pip)
```

---

## Dépendances principales

| Package | Version | Rôle |
|---|---|---|
| pandas | ≥2.0 | Manipulation données |
| plotly | ≥5.18 | Graphiques interactifs |
| streamlit | ≥1.30 | Application web |
| scikit-learn | ≥1.3 | Clustering, régression |
| statsmodels | ≥0.14 | ARIMA |
| prophet | ≥1.1 | Prévisions séries temporelles |
| requests | ≥2.31 | Clients HTTP |
| numpy | ≥1.26 | Calculs numériques |
