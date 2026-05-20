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

VIEW_SQL = """
CREATE OR REPLACE VIEW energy.consumption_weather AS
SELECT
    c.datetime, c.date, c.hour, c.day_of_week, c.is_weekend,
    c.consommation_brute_electricite_rte,
    w.temperature_2m, w.apparent_temperature, w.relative_humidity_2m,
    w.wind_speed_10m, w.precipitation, w.cloud_cover, w.surface_pressure
FROM energy.consumption c
LEFT JOIN energy.weather w ON c.datetime = w.datetime
"""


def _recreate_view(engine):
    """Crée ou remplace la vue croisée."""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text(VIEW_SQL))
        conn.commit()


def _append_new_rows(df: pd.DataFrame, table: str, key_cols: list, engine) -> int:
    """Insère uniquement les lignes absentes de la table (déduplication sur key_cols)."""
    from sqlalchemy import inspect as sa_inspect

    if not sa_inspect(engine).has_table(table, schema="energy"):
        df.to_sql(table, engine, schema="energy", if_exists="replace",
                  index=False, method="multi", chunksize=500)
        return len(df)

    existing = pd.read_sql(f"SELECT {', '.join(key_cols)} FROM energy.{table}", engine)

    def _norm(series: pd.Series) -> pd.Series:
        try:
            return pd.to_datetime(series, utc=True).astype("int64")
        except (TypeError, ValueError):
            return series.astype(str)

    df_keys = pd.DataFrame({c: _norm(df[c]) for c in key_cols})
    ex_keys = pd.DataFrame({c: _norm(existing[c]) for c in key_cols})

    existing_set = set(ex_keys.itertuples(index=False, name=None))
    mask = ~df_keys.apply(tuple, axis=1).isin(existing_set)

    new_rows = df[mask]
    if new_rows.empty:
        logger.info("Table %s: aucune nouvelle ligne à insérer", table)
        return 0

    new_rows.to_sql(table, engine, schema="energy", if_exists="append",
                    index=False, method="multi", chunksize=500)
    return len(new_rows)


def load_energy_to_db():
    """Charge les données énergie dans PostgreSQL (append, dédupliqué sur datetime + region_name)."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"
        if not latest_csv.exists():
            logger.warning("Fichier warehouse introuvable: %s", latest_csv)
            return

        df = pd.read_csv(latest_csv)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        if "date" not in df.columns:
            df["date"] = df["datetime"].dt.date

        key_cols = ["datetime", "region_name"] if "region_name" in df.columns else ["datetime"]
        inserted = _append_new_rows(df, "consumption", key_cols, engine)
        logger.info("Energie chargée en DB: %d nouvelles lignes (sur %d)", inserted, len(df))

    except ImportError:
        logger.error("sqlalchemy non installé — pip install sqlalchemy psycopg2-binary")
    except Exception as e:
        logger.error("Erreur chargement énergie: %s", e)
        raise


def load_weather_to_db():
    """Charge les données météo dans PostgreSQL (append, dédupliqué sur datetime + region)."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        meteo_files = sorted(RAW_METEO_DIR.glob("meteo_regions_*.csv"))
        if not meteo_files:
            logger.warning("Aucun fichier météo trouvé dans %s", RAW_METEO_DIR)
            return

        df = pd.read_csv(meteo_files[-1])
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        key_cols = ["datetime", "region"] if "region" in df.columns else ["datetime"]
        inserted = _append_new_rows(df, "weather", key_cols, engine)
        logger.info("Météo chargée en DB: %d nouvelles lignes (sur %d)", inserted, len(df))

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

    from sqlalchemy import create_engine
    _recreate_view(create_engine(DB_URL))
    logger.info("Vue energy.consumption_weather mise à jour")

    logger.info("Chargement terminé")


if __name__ == "__main__":
    main()
