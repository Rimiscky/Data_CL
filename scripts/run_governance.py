"""
Génère un rapport qualité des données pour toutes les régions.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import WAREHOUSE_DIR, QUALITY_DIR, REGIONS  # noqa: E402
from src.governance.quality import DataQualityChecker  # noqa: E402

logger = get_logger("run_governance")

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://airflow:airflow@postgres:5432/energy_db",
)


def run_quality_check(region: str):
    dataset_name = f"energy_consumption_{region}"
    latest_csv = WAREHOUSE_DIR / dataset_name / "latest.csv"

    if not latest_csv.exists():
        logger.warning("[%s] Fichier warehouse introuvable: %s", region.upper(), latest_csv)
        return None

    df = pd.read_csv(latest_csv)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    checker = DataQualityChecker(dataset_name=dataset_name)
    report = checker.run_all_checks(df)

    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    report_path = checker.save_report(report, QUALITY_DIR)

    logger.info(
        "[%s] score=%.1f%%, règles passées=%d/%d → %s",
        region.upper(),
        report.score,
        sum(1 for r in report.rules if r.passed),
        len(report.rules),
        report_path.name,
    )
    return report, report_path


def load_report_to_db(report):
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
        df.to_sql("quality_reports", engine, schema="energy", if_exists="append", index=False)
        logger.info("Rapport chargé en DB")
    except Exception as e:
        logger.warning("Chargement DB ignoré (pas de PostgreSQL local) : %s", e)


def main():
    logger.info("=" * 50)
    logger.info("  Gouvernance — Qualité des données")
    logger.info("  Régions : %s", ", ".join(REGIONS))
    logger.info("=" * 50)

    for region in REGIONS:
        result = run_quality_check(region)
        if result:
            report, report_path = result
            load_report_to_db(report)

    logger.info("Gouvernance terminée.")


if __name__ == "__main__":
    main()
