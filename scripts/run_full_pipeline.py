"""
Entrypoint Docker : orchestre Ingestion → ETL → Dashboard en appelant
directement les fonctions Python (sans subprocess).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import get_logger  # noqa: E402
from scripts.ingest import main as run_ingest  # noqa: E402
from scripts.run_etl import main as run_etl_pipeline  # noqa: E402
from scripts.run_dashboard import main as run_dashboard  # noqa: E402

logger = get_logger("full-pipeline")

STEPS = [
    ("Étape 1/3 : Ingestion", run_ingest),
    ("Étape 2/3 : ETL", run_etl_pipeline),
    ("Étape 3/3 : Dashboard", run_dashboard),
]


def main():
    logger.info("=" * 50)
    logger.info("  Pipeline complet — Énergie France")
    logger.info("=" * 50)

    for name, func in STEPS:
        logger.info(">>> %s...", name)
        try:
            func()
        except Exception as e:
            logger.error("Pipeline interrompu à %s: %s", name, e, exc_info=True)
            sys.exit(1)

    logger.info("=" * 50)
    logger.info("  Pipeline terminé avec succès !")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
