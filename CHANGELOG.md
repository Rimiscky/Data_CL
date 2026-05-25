# Changelog

Toutes les modifications notables du projet sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
versionnement [Semantic Versioning](https://semver.org/lang/fr/).

---

## [v1.3.0] — 2026-05-25

### Ajouté
- 3 nouveaux graphiques dans le dashboard IDF : profil 24h par saison, box plots par heure, heatmap calendrier Date × Heure (Viridis)
- Bouton `← Accueil` dans `dashboard_cross_energy_meteo.html`
- Données warehouse déployées sur EC2 pour les 3 régions manquantes (Provence, Bretagne, Nouvelle-Aquitaine)
- Documentation complète `docs/dashboards.md` : classes Python, pipeline de génération, déploiement EC2

### Corrigé
- Dashboard croisé énergie × météo : restauration des 6 graphiques via fusion `DataMerger.merge_energy_weather()`
- `CrossDashboardBuilder` : correction du constructeur (prend un DataFrame brut, pas une instance `DataAnalyzer`)

---

## [v1.2.0] — 2026-03-26

### Ajouté
- Déploiement Streamlit sur EC2 (port 8501, service systemd `streamlit.service`)
- Script `scripts/deploy_streamlit_ec2.sh` — déploiement automatisé avec installation des dépendances
- Script `scripts/cleanup_disk.sh` — nettoyage disque EC2 (Docker, logs, data/raw, APT/pip)
- Script `scripts/setup_cleanup_cron.sh` — installation du cron de nettoyage (dimanche 3h UTC)
- Migration complète GitLab CI/CD (suppression GitHub Actions)
- `.gitlab-ci.yml` : stages `test` (lint + tests Python 3.11/3.12 + Docker) + `deploy` (EC2 self-hosted runner) + `pipeline` (manuel)
- Self-hosted runner GitLab sur EC2 pour le déploiement

### Modifié
- `index.html` : lien Streamlit mis à jour vers `http://13.39.99.56:8501`
- Clé RTE API via `EnvironmentFile=/home/ubuntu/.env` (systemd)
- `config/settings.py` : `PROJECT_DIR` corrigé vers `/home/ubuntu`

### Corrigé
- `${DRY_RUN:+ (dry-run)}` affiché systématiquement — corrigé via test explicite `[[ "$DRY_RUN" == "true" ]]`
- `pip3: command not found` sur Ubuntu 22.04 — installation préalable `python3-pip`

---

## [v1.1.0] — 2026-03-21

### Ajouté
- Application Streamlit multi-onglets (`app_streamlit.py`) avec 6 onglets :
  - Vue d'ensemble (KPIs, delta vs période précédente)
  - Consommation (profil horaire, heatmap, distribution, anomalies)
  - Météo × Énergie (corrélations croisées, scatter, heatmap de corrélation)
  - Mix de production RTE (nucléaire, éolien, solaire…)
  - Gouvernance (score qualité, rapports)
  - Prévisions 30 jours Prophet + intervalle de confiance 95%
- Filtres sidebar : région (4 régions), période (7j/30j/90j/personnalisée), seuil d'alerte
- Export CSV et PNG sur tous les graphiques
- Alertes de seuil de consommation
- Slider horizon de prévision J+3 / J+7 / J+14
- Dashboard comparaison : animations CSS/JS, bouton retour, CDN Plotly 2.27.0
- Dashboard IDF : filtres JS client-side (date, saison, jour, heure), bannière no-data, KPIs animés
- Animations : `fadeInUp`, `slideDown`, `kpiBounce`, `shimmer`, compteurs `easeOutCubic`
- API RTE migrée vers OAuth2 officiel (`actual_generations_per_production_type`)

### Modifié
- CDN Plotly fixé à `2.27.0` dans tous les dashboards HTML (suppression de `plotly-latest`)

---

## [v1.0.0] — 2026-03-15

### Ajouté
- Pipeline de données complet : ingestion → ETL → gouvernance → dashboards
- **Ingestion multi-sources** :
  - API ODRE (consommation régionale brute, 4 régions)
  - API Open-Meteo (météo historique horaire, sans clé)
  - API RTE génération électrique (OAuth2)
- **ETL** (`src/etl/`) : normalisation colonnes, conversion UTC, enrichissement temporel, fusion énergie × météo (`merge_asof`, tolérance 1h)
- **Gouvernance des données** : score qualité 0–100%, rapports JSON, lignage, catalogue
- **Dashboards HTML** :
  - `dashboard_energy_idf.html` — profil horaire, journalier, heatmap, anomalies z-score
  - `dashboard_comparaison.html` — comparaison inter-régionale, radar saisonnier
  - `dashboard_cross_energy_meteo.html` — corrélation énergie × météo
  - `index.html` — page d'accueil
- **Orchestration Airflow** (`airflow/dags/energy_pipeline_dag.py`) — DAG quotidien 6h UTC, ingestions en parallèle, alertes e-mail
- **Infrastructure Docker** : `Dockerfile` multi-stage (`test` + `production`), `docker-compose.yml`
- **Monitoring** : exporteur Prometheus, dashboards Grafana
- **PostgreSQL** : schéma `energy` (consumption, weather, rte_generation, quality_reports)
- **MinIO** : stockage objet compatible S3
- Déploiement EC2 AWS (Ubuntu 22.04, Paris `eu-west-3`)

---

[v1.3.0]: https://gitlab.com/Rimiscky/data_cl/-/compare/v1.2.0...v1.3.0
[v1.2.0]: https://gitlab.com/Rimiscky/data_cl/-/compare/v1.1.0...v1.2.0
[v1.1.0]: https://gitlab.com/Rimiscky/data_cl/-/compare/v1.0.0...v1.1.0
[v1.0.0]: https://gitlab.com/Rimiscky/data_cl/-/commits/v1.0.0
