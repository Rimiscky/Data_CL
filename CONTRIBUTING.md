# Guide de contribution

## Workflow Git

### Branches

| Branche | Rôle |
|---|---|
| `main` | Production — code stable déployé sur EC2 |
| `develop` | Intégration — fonctionnalités terminées en attente de release |
| `feature/<nom>` | Nouvelle fonctionnalité |
| `fix/<nom>` | Correction de bug |
| `docs/<nom>` | Documentation uniquement |

### Cycle de travail

```bash
# 1. Partir de develop
git checkout develop && git pull gitlab develop

# 2. Créer une branche
git checkout -b feature/ma-fonctionnalite

# 3. Travailler, commiter
git add src/mon_fichier.py
git commit -m "feat: description courte de la fonctionnalité"

# 4. Pousser et ouvrir une Merge Request vers develop
git push gitlab feature/ma-fonctionnalite
```

### Convention de commits

Format : `<type>(<scope>): <description>`

| Type | Quand l'utiliser |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `refactor` | Refactoring sans changement de comportement |
| `test` | Ajout ou modification de tests |
| `ci` | Modification du pipeline CI/CD |
| `chore` | Tâches de maintenance (dépendances, config) |

**Exemples :**
```
feat(dashboard): ajouter graphique consommation horaire par région
fix(etl): corriger la gestion des valeurs nulles dans le merger
docs(readme): mettre à jour les prérequis d'installation
ci(gitlab): ajouter stage de déploiement staging
```

---

## Environnement de développement

### Prérequis

- Python 3.11 ou 3.12
- Docker (optionnel, pour les tests complets)
- Clé API RTE (variable `RTE_API_KEY`) pour l'ingestion RTE

### Installation

```bash
git clone git@gitlab.com:Rimiscky/data_cl.git
cd data_cl
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Variables d'environnement

Créer un fichier `.env` à la racine (jamais commité) :

```bash
RTE_API_KEY=<ton_token_base64>
```

### Lancer les tests

```bash
# Tests unitaires
python -m pytest tests/ -v

# Lint
flake8 src/ scripts/ --max-line-length=120

# Via Docker (identique à la CI)
docker build --target test -t pipeline-test .
docker run --rm pipeline-test python -m pytest tests/ -v
```

---

## Structure du projet

```
Data_CL/
├── .gitlab-ci.yml              # Pipeline CI/CD GitLab
├── Dockerfile                  # Image Docker multi-stage
├── requirements.txt            # Dépendances Python
├── app_streamlit.py            # Application Streamlit (6 onglets)
├── config/
│   └── settings.py             # Configuration centralisée (chemins, régions, API)
├── src/
│   ├── ingestion/              # Clients API (ODRE, Open-Meteo, RTE)
│   ├── etl/                    # Extraction, transformation, fusion, chargement
│   ├── analysis/               # Analyseur + constructeurs de dashboards
│   ├── governance/             # Qualité, lignage, catalogue
│   ├── monitoring/             # Exporteur Prometheus
│   └── utils/                  # Logger
├── scripts/
│   ├── ingest.py               # Ingestion multi-sources
│   ├── run_etl.py              # Pipeline ETL
│   ├── run_dashboard.py        # Génération dashboards HTML
│   ├── run_governance.py       # Contrôles qualité
│   ├── run_full_pipeline.py    # Pipeline complet (ingest → ETL → dashboard → gouvernance)
│   ├── deploy_ec2.sh           # Déploiement dashboards HTML sur EC2
│   ├── deploy_streamlit_ec2.sh # Déploiement app Streamlit sur EC2
│   └── cleanup_disk.sh         # Nettoyage disque EC2
├── tests/                      # Tests unitaires pytest
├── docs/                       # Documentation technique
│   ├── dashboards.md           # Dashboards : création et utilisation
│   ├── pipeline.md             # Pipeline de données : détail de chaque étape
│   └── apis_explication.md     # Détail des API sources
├── airflow/dags/               # DAG Airflow quotidien
├── data/                       # Ignoré par git
│   ├── raw/                    # Data Lake brut
│   ├── warehouse/              # Données transformées
│   └── governance/             # Rapports qualité
└── output/dashboards/          # Dashboards HTML générés (ignorés par git)
```

---

## Pipeline CI/CD GitLab

Chaque push déclenche automatiquement :

```
push → test:py311 ──┐
     → test:py312 ──┼──→ docker:test ──→ deploy:ec2 (main seulement)
     → lint:flake8 ─┘
```

Les secrets sont stockés dans **GitLab CI/CD Variables** :
`Settings → CI/CD → Variables` (jamais dans le code).

| Variable | Description |
|---|---|
| `RTE_API_KEY` | Token OAuth2 RTE (Base64) |
| `AIRFLOW_SMTP_PASSWORD` | Mot de passe SMTP pour alertes Airflow |

---

## Versionnement

Le projet suit [Semantic Versioning](https://semver.org/lang/fr/) :
- `MAJOR` — changement incompatible (modification du schéma warehouse, suppression d'une API)
- `MINOR` — nouvelle fonctionnalité rétrocompatible
- `PATCH` — correction de bug

Les tags sont créés sur `main` après chaque release :
```bash
git tag -a v1.4.0 -m "Release v1.4.0 — description"
git push gitlab v1.4.0
```

Voir le [CHANGELOG](CHANGELOG.md) pour l'historique complet.
