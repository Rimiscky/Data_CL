"""
Script d'exécution du pipeline ETL — multi-régions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.pipeline import ETLPipeline  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import RAW_API_DIR, WAREHOUSE_DIR, REGIONS  # noqa: E402

logger = get_logger("run_etl")


def run_region(region: str) -> bool:
    logger.info("─" * 50)
    logger.info("  ETL région : %s", region.upper())
    logger.info("─" * 50)

    pipeline = ETLPipeline(
        data_lake_dir=RAW_API_DIR,
        warehouse_dir=WAREHOUSE_DIR,
        table_name=f"energy_consumption_{region}",
        file_prefix=f"odre_consommation_{region}_",
    )

    result = pipeline.run(
        source_extension="json",
        transform_strategy="fill_zero",
        partition=True,
    )

    if result.success:
        logger.info(
            "[%s] OK — %d lignes → %s (%.2fs)",
            region.upper(), result.rows_loaded, result.output_path, result.duration_seconds,
        )
    else:
        logger.error("[%s] ÉCHEC : %s", region.upper(), result.errors)

    return result.success


def main():
    logger.info("=" * 50)
    logger.info("  Pipeline ETL — Consommation énergétique")
    logger.info("  Régions : %s", ", ".join(REGIONS))
    logger.info("=" * 50)

    successes, failures = [], []
    for region in REGIONS:
        ok = run_region(region)
        (successes if ok else failures).append(region)

    logger.info("=" * 50)
    logger.info("Résumé ETL : %d OK / %d échoués", len(successes), len(failures))
    if successes:
        logger.info("  ✓ %s", ", ".join(successes))
    if failures:
        logger.warning("  ✗ %s", ", ".join(failures))
    logger.info("=" * 50)

    if failures and not successes:
        sys.exit(1)


if __name__ == "__main__":
    main()
