"""
Script d'exécution du pipeline ETL — Jour 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.pipeline import ETLPipeline  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import RAW_API_DIR, WAREHOUSE_DIR  # noqa: E402

logger = get_logger("run_etl")


def main():
    logger.info("=" * 50)
    logger.info("  Pipeline ETL — Consommation énergétique IDF")
    logger.info("=" * 50)

    pipeline = ETLPipeline(
        data_lake_dir=RAW_API_DIR,
        warehouse_dir=WAREHOUSE_DIR,
        table_name="energy_consumption_idf",
    )

    result = pipeline.run(
        source_extension="json",
        transform_strategy="fill_zero",
        partition=True,
    )

    if result.success:
        logger.info("Pipeline terminé avec succès !")
        logger.info("  → Lignes extraites  : %d", result.rows_extracted)
        logger.info("  → Lignes chargées   : %d", result.rows_loaded)
        logger.info("  → Fichier sortie    : %s", result.output_path)
        logger.info("  → Manifeste         : %s", result.manifest_path)
        logger.info("  → Durée             : %.2fs", result.duration_seconds)
    else:
        logger.error("Pipeline échoué !")
        for err in result.errors:
            logger.error("  → %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
