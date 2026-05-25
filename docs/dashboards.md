# Documentation — Dashboards Énergie France

## Vue d'ensemble

Le projet expose **4 interfaces de visualisation** qui couvrent la consommation électrique et les données météo pour 4 régions françaises (IDF, Provence-Alpes-Côte d'Azur, Bretagne, Nouvelle-Aquitaine).

| Interface | Technologie | Accès local | Accès production |
|---|---|---|---|
| Page d'accueil | HTML statique | `output/dashboards/index.html` | `http://13.39.99.56:8080` |
| Dashboard IDF | HTML + Plotly | `output/dashboards/dashboard_energy_idf.html` | `http://13.39.99.56:8080/dashboard_energy_idf.html` |
| Dashboard Comparaison | HTML + Plotly | `output/dashboards/dashboard_comparaison.html` | `http://13.39.99.56:8080/dashboard_comparaison.html` |
| Dashboard Énergie × Météo | HTML + Plotly | `output/dashboards/dashboard_cross_energy_meteo.html` | `http://13.39.99.56:8080/dashboard_cross_energy_meteo.html` |
| Application Streamlit | Python / Streamlit | `http://localhost:8501` | `http://13.39.99.56:8501` |

---

## 1. Dashboard Énergie IDF (`dashboard_energy_idf.html`)

### Description

Dashboard HTML autonome (fichier unique) avec données embarquées en JSON. Aucune dépendance serveur — ouvrable directement dans un navigateur.

### Graphiques (9 au total)

| ID | Titre | Type |
|---|---|---|
| `#c-hourly` | Profil horaire moyen | Courbe avec plage min/max |
| `#c-daily` | Consommation journalière | Barres |
| `#c-weekly` | Semaine vs week-end | Courbes superposées |
| `#c-weekday` | Profil hebdomadaire | Courbe par jour de semaine |
| `#c-heatmap` | Heatmap Heure × Jour de semaine | Heatmap colorée |
| `#c-anomaly` | Détection d'anomalies (z-score) | Scatter avec alertes rouges |
| `#c-season` | Profil 24h par saison | Multi-lignes (4 couleurs) |
| `#c-boxhour` | Distribution par heure (boxplots) | Box plots Q1/médiane/Q3 |
| `#c-calheat` | Heatmap calendrier Date × Heure | Heatmap Viridis |

### Filtres interactifs (côté client, JavaScript)

- **Plage de dates** — sélecteur date début / fin
- **Saison** — Printemps, Été, Automne, Hiver, Toutes
- **Type de jour** — Semaine, Week-end, Tous
- **Tranche horaire** — Heures de pointe (7h–22h), Heures creuses (22h–7h), Toutes

Chaque filtre déclenche `updateAll()` qui appelle `Plotly.react()` sur les 9 graphiques.

### Génération

```bash
python scripts/run_dashboard.py
```

Ce script :
1. Charge `data/warehouse/energy_consumption_idf/latest.csv`
2. Récupère la météo Open-Meteo (pour la période couverte par les données)
3. Fusionne énergie + météo via `DataMerger.merge_energy_weather()`
4. Génère `output/dashboards/dashboard_energy_idf.html` via `DashboardBuilder`

### Classe Python

```python
from src.analysis import DataAnalyzer, DashboardBuilder

analyzer = DataAnalyzer(df)           # df = DataFrame énergie
builder  = DashboardBuilder(analyzer, output_dir=Path("output/dashboards"))
builder.build_all()                   # construit les 6 graphiques de base
builder.build_rte_mix(rte_records)    # ajoute le graphique mix RTE (optionnel)
html_path = builder.export_html()
```

`export_html()` injecte les données (500 lignes max) en JSON dans le template HTML et écrit le fichier.

---

## 2. Dashboard Comparaison (`dashboard_comparaison.html`)

### Description

Dashboard HTML statique de comparaison entre 2 régions. Généré une seule fois et servi tel quel (pas de régénération automatique dans le pipeline actuel).

### Graphiques (5)

- Évolution temporelle superposée des 2 régions
- Profil horaire comparatif
- Profil saisonnier radar
- Boxplots côte à côte
- Écart quotidien région A − région B

### Filtres

- Sélection des 2 régions (parmi les 4 disponibles)
- Saison
- Type de jour

### Génération

Ce fichier est généré par `scripts/run_analysis.py`. En cas de régénération manuelle :

```bash
python scripts/run_analysis.py
```

---

## 3. Dashboard Énergie × Météo (`dashboard_cross_energy_meteo.html`)

### Description

Dashboard croisé qui visualise l'impact des conditions météorologiques sur la consommation électrique. Nécessite des données fusionnées (énergie + météo) — la colonne `temperature_2m` doit être présente dans le DataFrame.

### Graphiques (6)

| Graphique | Description |
|---|---|
| Énergie vs Température | Double axe Y : consommation (MW) + température (°C) avec range slider |
| Scatter Température → Consommation | Nuage de points coloré par période du jour + courbe de tendance polynomiale degré 2 |
| Impact météo par catégorie | Barres : consommation moyenne par catégorie de température (gel → canicule) avec barres d'erreur |
| Heatmap de corrélation | Matrice de corrélation entre toutes les variables énergie et météo |
| Analyse vent & pluie | Consommation selon la force du vent et les conditions de pluie |
| Vue journalière synthèse | Sous-graphes superposés : barres de conso + courbe température |

### Prérequis données

Le DataFrame doit contenir `temperature_2m`. Si la colonne est absente, les graphiques affichent "Données manquantes" à la place.

### Génération

```bash
python scripts/run_dashboard.py
```

Le script fusionne automatiquement les données météo avec le warehouse. Le dashboard croisé n'est généré que si la fusion réussit (`has_meteo = True`).

### Classe Python

```python
from src.analysis.cross_dashboard import CrossDashboardBuilder
from src.etl.merger import DataMerger

merger    = DataMerger()
merged_df = merger.merge_energy_weather(energy_df, meteo_df)
merged_df = merger.add_weather_categories(merged_df)   # ajoute temp_category, wind_category…

builder   = CrossDashboardBuilder(merged_df, output_dir=Path("output/dashboards"))
builder.build_all()
html_path = builder.export_html()   # → dashboard_cross_energy_meteo.html
```

**Important :** `CrossDashboardBuilder` prend un DataFrame brut, pas une instance de `DataAnalyzer`.

---

## 4. Application Streamlit (`app_streamlit.py`)

### Description

Application web interactive multi-onglets. Contrairement aux dashboards HTML, les données sont chargées dynamiquement depuis le warehouse au démarrage — les filtres déclenchent un rechargement côté Python.

### Onglets

| Onglet | Contenu |
|---|---|
| **Vue d'ensemble** | KPIs (consommation moy., pic, min, gaz), graphique temporel, profil horaire |
| **Consommation** | Analyse détaillée : profil saisonnier, heatmap heure×jour, distribution, anomalies |
| **Météo × Énergie** | Fusion dynamique Open-Meteo + dashboard croisé embarqué |
| **Mix de production** | Mix électrique RTE (nucléaire, solaire, éolien…) |
| **Gouvernance** | Score qualité des données, rapport de lineage, catalogue |
| **Prévisions** | Prévisions 30 jours avec Prophet + intervalle de confiance 95% + export CSV |

### Filtres (sidebar)

- **Région** — parmi les 4 régions configurées dans `REGION_LABELS`
- **Période** — 7 jours / 30 jours / 90 jours / Tout / Personnalisée
- **Alertes de seuil** — seuil MW configurable, déclenche une alerte visuelle

### Lancer localement

```bash
streamlit run app_streamlit.py
# Accès : http://localhost:8501
```

### Ajouter une région

1. Ajouter la clé dans `REGION_LABELS` (fichier `app_streamlit.py`, ligne ~113) :
   ```python
   REGION_LABELS = {
       "idf":                "Île-de-France",
       "provence":           "Provence-Alpes-Côte d'Azur",
       "bretagne":           "Bretagne",
       "nouvelle-aquitaine": "Nouvelle-Aquitaine",
       "ma-region":          "Ma Nouvelle Région",   # ← ajouter ici
   }
   ```
2. Ingérer les données pour cette région :
   ```bash
   python scripts/ingest.py          # ingère toutes les régions listées dans config/settings.py
   python scripts/run_etl.py         # transforme et charge dans le warehouse
   ```
3. Le fichier `data/warehouse/energy_consumption_ma-region/latest.csv` doit exister — la région apparaît alors automatiquement dans la sidebar sans message "données manquantes".

---

## Pipeline de génération complet

```
data/raw/api/           data/raw/meteo/
      │                       │
      ▼                       ▼
  run_etl.py          MeteoClient (Open-Meteo)
      │                       │
      ▼                       ▼
data/warehouse/         DataMerger.merge_energy_weather()
energy_consumption_*          │
      │                       │
      └──────────┬────────────┘
                 ▼
         run_dashboard.py
                 │
         ┌───────┴────────────┐
         ▼                    ▼
  DashboardBuilder    CrossDashboardBuilder
         │                    │
         ▼                    ▼
dashboard_energy_idf  dashboard_cross_energy_meteo
      .html                 .html
```

Commande unique pour tout régénérer :

```bash
python scripts/run_full_pipeline.py
```

---

## Déploiement sur EC2

### Structure sur le serveur

```
/home/ubuntu/
├── app_streamlit.py
├── src/                          # code source Python
├── config/                       # paramètres
├── data/
│   ├── warehouse/
│   │   ├── energy_consumption_idf/latest.csv
│   │   ├── energy_consumption_provence/latest.csv
│   │   ├── energy_consumption_bretagne/latest.csv
│   │   └── energy_consumption_nouvelle-aquitaine/latest.csv
│   └── raw/
│       ├── meteo/
│       └── rte/
└── www/dashboards/               # fichiers servis sur port 8080
    ├── index.html
    ├── dashboard_energy_idf.html
    ├── dashboard_comparaison.html
    └── dashboard_cross_energy_meteo.html
```

### Mettre à jour les dashboards HTML sur EC2

```bash
# Régénérer localement
python scripts/run_dashboard.py

# Déployer
scp -i ~/Downloads/Projet_Data_Engineering.pem \
  output/dashboards/dashboard_energy_idf.html \
  output/dashboards/dashboard_cross_energy_meteo.html \
  ubuntu@13.39.99.56:/home/ubuntu/www/dashboards/
```

### Mettre à jour le Streamlit sur EC2

```bash
bash scripts/deploy_streamlit_ec2.sh
```

Ou manuellement après modification de `app_streamlit.py` :

```bash
scp -i ~/Downloads/Projet_Data_Engineering.pem app_streamlit.py ubuntu@13.39.99.56:/home/ubuntu/
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 "sudo systemctl restart streamlit"
```

### Vérifier l'état des services

```bash
ssh -i ~/Downloads/Projet_Data_Engineering.pem ubuntu@13.39.99.56 \
  "sudo systemctl status streamlit --no-pager && curl -s -o /dev/null -w '%{http_code}' http://localhost:8080"
```

---

## CDN et dépendances frontend

Tous les dashboards HTML utilisent Plotly **2.27.0** fixé via CDN :

```html
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
```

La version est fixée (pas `plotly-latest`) pour garantir la stabilité des rendus en production. En cas de mise à jour, modifier toutes les occurrences dans :
- `src/analysis/dashboard.py` (template `_DASHBOARD_HTML_TEMPLATE`)
- `src/analysis/cross_dashboard.py` (méthode `export_html`)
- `output/dashboards/dashboard_comparaison.html` (fichier statique)
