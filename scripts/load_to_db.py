"""
Script de chargement des données warehouse → PostgreSQL.
Insère les données énergie et météo dans la base energy_db.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.utils.logger import get_logger  # noqa: E402
from config.settings import WAREHOUSE_DIR, RAW_METEO_DIR  # noqa: E402

logger = get_logger("load_to_db")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://airflow:airflow@postgres:5432/energy_db",
)


def load_energy_to_db():
    """Charge les données énergie dans PostgreSQL."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"
        if not latest_csv.exists():
            logger.warning("Fichier warehouse introuvable: %s", latest_csv)
            return

        df = pd.read_csv(latest_csv)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        if "date" not in df.columns and "datetime" in df.columns:
            df["date"] = df["datetime"].dt.date

        df.to_sql(
            "consumption",
            engine,
            schema="energy",
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=500,
        )
        logger.info("Energie chargée en DB: %d lignes", len(df))

    except ImportError:
        logger.error("sqlalchemy non installé — pip install sqlalchemy psycopg2-binary")
    except Exception as e:
        logger.error("Erreur chargement énergie: %s", e)
        raise


def load_weather_to_db():
    """Charge les données météo dans PostgreSQL."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        meteo_files = sorted(RAW_METEO_DIR.glob("meteo_idf_*.csv"))
        if not meteo_files:
            logger.warning("Aucun fichier météo trouvé dans %s", RAW_METEO_DIR)
            return

        df = pd.read_csv(meteo_files[-1])
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        df.to_sql(
            "weather",
            engine,
            schema="energy",
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=500,
        )
        logger.info("Météo chargée en DB: %d lignes", len(df))

    except ImportError:
        logger.error("sqlalchemy non installé — pip install sqlalchemy psycopg2-binary")
    except Exception as e:
        logger.error("Erreur chargement météo: %s", e)
        raise


def load_quality_to_db():
    """Charge le dernier rapport qualité dans PostgreSQL."""
    try:
        import json
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        from config.settings import QUALITY_DIR
        quality_files = sorted(QUALITY_DIR.glob("quality_*.json"))
        if not quality_files:
            return

        with open(quality_files[-1]) as f:
            report = json.load(f)

        df = pd.DataFrame([{
            "dataset_name": report["dataset_name"],
            "score": report["score"],
            "total_rows": report["total_rows"],
            "total_columns": report["total_columns"],
            "passed": report["passed"],
            "report_json": json.dumps(report),
        }])

        df.to_sql(
            "quality_reports",
            engine,
            schema="energy",
            if_exists="append",
            index=False,
        )
        logger.info("Rapport qualité chargé en DB")

    except Exception as e:
        logger.error("Erreur chargement qualité: %s", e)


def main():
    logger.info("=" * 50)
    logger.info("  Chargement données → PostgreSQL (energy_db)")
    logger.info("=" * 50)

    load_energy_to_db()
    load_weather_to_db()
    load_quality_to_db()

    logger.info("Chargement terminé")


if __name__ == "__main__":
    main()
