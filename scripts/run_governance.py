"""
Génère un rapport qualité des données et le charge dans PostgreSQL.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import WAREHOUSE_DIR, QUALITY_DIR  # noqa: E402
from src.governance.quality import DataQualityChecker  # noqa: E402

logger = get_logger("run_governance")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://airflow:airflow@postgres:5432/energy_db",
)


def run_quality_check():
    """Lance le contrôle qualité et sauvegarde le rapport."""
    latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"
    if not latest_csv.exists():
        logger.warning("Fichier warehouse introuvable: %s", latest_csv)
        return None

    df = pd.read_csv(latest_csv)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    checker = DataQualityChecker(dataset_name="energy_consumption_idf")
    report = checker.run_all_checks(df)

    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = checker.save_report(report, QUALITY_DIR)

    logger.info(
        "Rapport qualité: score=%.1f%%, règles passées=%d/%d",
        report.score,
        sum(1 for r in report.rules if r.passed),
        len(report.rules),
    )
    return report, report_path


def load_report_to_db(report):
    """Insère le rapport dans PostgreSQL."""
    try:
        import json
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL)

        report_dict = report.to_dict()
        df = pd.DataFrame([{
            "dataset_name": report_dict["dataset_name"],
            "score": report_dict["score"],
            "total_rows": report_dict["total_rows"],
            "total_columns": report_dict["total_columns"],
            "passed": report_dict["passed"],
            "report_json": json.dumps(report_dict),
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
        logger.error("Erreur chargement rapport: %s", e)


def main():
    logger.info("=" * 50)
    logger.info("  Gouvernance des données — Qualité")
    logger.info("=" * 50)

    result = run_quality_check()
    if result:
        report, report_path = result
        logger.info("Rapport sauvegardé: %s", report_path)
        load_report_to_db(report)

    logger.info("Gouvernance terminée")


if __name__ == "__main__":
    main()
