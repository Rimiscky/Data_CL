"""
Configuration centralisée du projet.
"""
import os
from pathlib import Path

# Chemins du projet
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_API_DIR = DATA_DIR / "raw" / "api"
RAW_SCRAPING_DIR = DATA_DIR / "raw" / "scraping"
RAW_RTE_DIR = DATA_DIR / "raw" / "rte"
RAW_METEO_DIR = DATA_DIR / "raw" / "meteo"
PROCESSED_DIR = DATA_DIR / "processed"
WAREHOUSE_DIR = DATA_DIR / "warehouse"

# API ODRE - Consommation énergétique (multi-régional)
ODRE_BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1"
ODRE_DATASET = "consommation-quotidienne-brute-regionale"
ODRE_REGION = "Île-de-France"
ODRE_ROWS_LIMIT = 100

# Scraping - RTE éCO2mix données régionales
RTE_ECO2MIX_URL = "https://www.rte-france.com/eco2mix/les-donnees-regionales"

# API RTE — Données de génération en temps réel
# Token OAuth2 Base64 (client_id:client_secret encodé en base64)
RTE_API_KEY = os.getenv("RTE_API_KEY", "")

# API Open-Meteo — Données météo historiques (gratuit, sans clé)
OPENMETEO_BASE_URL = "https://archive-api.open-meteo.com/v1"

# API Météo-Concept — Données régionales (nécessite clé)
METEO_FRANCE_BASE_URL = "https://api.meteo-concept.com/api"
METEO_FRANCE_API_KEY = os.getenv("METEO_FRANCE_API_KEY", "")

# Coordonnées IDF par défaut
IDF_LATITUDE = 48.8566
IDF_LONGITUDE = 2.3522

# Configuration multi-régions
REGIONS = ["idf", "provence", "bretagne", "nouvelle-aquitaine"]
REGION_COORDINATES = {
    "idf": (48.8566, 2.3522),  # Paris
    "provence": (43.5, 5.5),   # Aix-en-Provence
    "bretagne": (48.1, -3.3),  # Rennes
    "nouvelle-aquitaine": (46.0, -0.5),  # Bordeaux
}
REGION_ODRE_NAMES = {
    "idf": "Île-de-France",
    "provence": "Provence-Alpes-Côte d'Azur",
    "bretagne": "Bretagne",
    "nouvelle-aquitaine": "Nouvelle-Aquitaine",
}

# Data Governance
GOVERNANCE_DIR = DATA_DIR / "governance"
CATALOG_DIR = GOVERNANCE_DIR / "catalog"
LINEAGE_DIR = GOVERNANCE_DIR / "lineage"
QUALITY_DIR = GOVERNANCE_DIR / "quality"

# Paramètres généraux
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
