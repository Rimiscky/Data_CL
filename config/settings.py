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
PROCESSED_DIR = DATA_DIR / "processed"
WAREHOUSE_DIR = DATA_DIR / "warehouse"

# API ODRE - Consommation énergétique Île-de-France
ODRE_BASE_URL = "https://odre.opendatasoft.com/api/explore/v2.1"
ODRE_DATASET = "consommation-quotidienne-brute-regionale"
ODRE_REGION = "Île-de-France"
ODRE_ROWS_LIMIT = 100

# Scraping - RTE éCO2mix données régionales
RTE_ECO2MIX_URL = "https://www.rte-france.com/eco2mix/les-donnees-regionales"

# Paramètres généraux
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2
