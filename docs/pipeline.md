# Pipeline de données — Guide d'utilisation

## Lancer le pipeline complet

```bash
python scripts/run_full_pipeline.py
```

Cette commande enchaîne toutes les étapes dans l'ordre.

---

## Étapes détaillées

### Étape 1 — Ingestion

```bash
python scripts/ingest.py
```

**Ce que ça fait :**
1. Interroge l'API ODRE pour les 4 régions (`idf`, `provence`, `bretagne`, `nouvelle-aquitaine`) — 500 enregistrements max par région
2. Récupère la météo Open-Meteo pour les 90 derniers jours (4 villes)
3. Récupère le mix de génération électrique RTE

**Sortie :**
```
data/raw/api/odre_consommation_idf_<timestamp>.json
data/raw/api/odre_consommation_provence_<timestamp>.json
data/raw/meteo/meteo_regions_<timestamp>.csv
data/raw/rte/rte_generation_mix_<timestamp>.json
```

**Prérequis :** `RTE_API_KEY` dans `.env` ou variable d'environnement.

---

### Étape 2 — ETL

```bash
python scripts/run_etl.py
```

**Ce que ça fait :**
- Charge le fichier JSON le plus récent depuis `data/raw/api/odre_consommation_<region>_*.json`
- Applique les transformations (normalisation, UTC, enrichissement temporel)
- Sauvegarde dans le warehouse

**Sortie :**
```
data/warehouse/energy_consumption_idf/latest.csv         ← 500 lignes, ~24 colonnes
data/warehouse/energy_consumption_idf/year=2026/data_<ts>.csv
data/warehouse/energy_consumption_provence/latest.csv
...
```

**Colonnes clés du warehouse :**

| Colonne | Type | Description |
|---|---|---|
| `datetime` | datetime UTC | Horodatage |
| `elec_consumption_mw` | int | Consommation électrique brute (MW) |
| `gas_consumption_mw` | float | Consommation gaz (MW) |
| `total_consumption_mw` | float | Total énergie |
| `year`, `month`, `day`, `hour` | int | Composantes temporelles |
| `is_weekend` | bool | Vrai si samedi ou dimanche |
| `elec_change_mw` | float | Variation vs enregistrement précédent |

---

### Étape 3 — Dashboards

```bash
python scripts/run_dashboard.py
```

**Ce que ça fait :**
1. Charge `data/warehouse/energy_consumption_idf/latest.csv`
2. Récupère la météo Open-Meteo pour la période couverte
3. Fusionne énergie + météo (`DataMerger`)
4. Génère `dashboard_energy_idf.html` (9 graphiques)
5. Génère `dashboard_cross_energy_meteo.html` (6 graphiques, si météo disponible)

**Sortie :**
```
output/dashboards/dashboard_energy_idf.html
output/dashboards/dashboard_cross_energy_meteo.html
```

---

### Étape 4 — Gouvernance

```bash
python scripts/run_governance.py
```

**Ce que ça fait :**
- Contrôle qualité sur chaque région (7 règles : complétude, doublons, plages valides, cohérence temporelle…)
- Score 0–100 %, sauvegarde rapport JSON
- Mise à jour du lignage et du catalogue

**Sortie :**
```
data/governance/quality/quality_energy_<region>.json
data/governance/lineage/lineage_<pipeline>_<timestamp>.json
data/governance/catalog/catalog.json
```

---

## Orchestration Airflow

Le DAG `energy_pipeline_multi_sources` tourne chaque jour à **6h UTC** :

```python
# airflow/dags/energy_pipeline_dag.py
schedule_interval="0 6 * * *"
```

**Graphe d'exécution :**
```
ingest_odre_idf ──────────────┐
ingest_odre_provence ─────────┤
ingest_odre_bretagne ─────────┼──→ run_etl ──→ run_governance ──→ generate_dashboard ──→ cleanup
ingest_odre_nouvelle_aq ──────┤
ingest_meteo ─────────────────┤
ingest_rte ───────────────────┘
```

Les ingestions sont parallèles. En cas d'échec, une alerte e-mail est envoyée via SMTP Gmail.

---

## Déploiement EC2

### Dashboards HTML

```bash
# Régénérer localement
python scripts/run_dashboard.py

# Déployer sur EC2
bash scripts/deploy_ec2.sh
```

### Application Streamlit

```bash
bash scripts/deploy_streamlit_ec2.sh
```

### Mettre à jour les données d'une région

```bash
# Copier directement le latest.csv
scp -i ~/Downloads/Projet_Data_Engineering.pem \
  data/warehouse/energy_consumption_<region>/latest.csv \
  ubuntu@13.39.99.56:/home/ubuntu/data/warehouse/energy_consumption_<region>/latest.csv

# Redémarrer Streamlit pour prendre en compte
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 \
  "sudo systemctl restart streamlit"
```

---

## Dépannage

### "Pas de données pour cette région"
Le fichier `data/warehouse/energy_consumption_<region>/latest.csv` n'existe pas sur EC2.
```bash
scp -i ~/Downloads/Projet_Data_Engineering.pem \
  data/warehouse/energy_consumption_<region>/latest.csv \
  ubuntu@13.39.99.56:/home/ubuntu/data/warehouse/energy_consumption_<region>/
```

### Dashboard croisé — 2 graphiques au lieu de 6
La colonne `temperature_2m` est absente du DataFrame. Relancer `run_dashboard.py` qui récupère la météo et fusionne.

### "No module named streamlit" sur EC2
```bash
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 \
  "sudo apt-get install -y python3-pip && pip3 install streamlit pandas plotly numpy scikit-learn statsmodels prophet"
```

### Vérifier l'état des services EC2
```bash
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 \
  "sudo systemctl status streamlit --no-pager && \
   curl -s -o /dev/null -w 'HTTP dashboards: %{http_code}\n' http://localhost:8080"
```
