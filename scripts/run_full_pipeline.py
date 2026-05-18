"""
Script d'orchestration du pipeline complet : Ingestion → ETL.
Utilisé comme entrypoint du service Docker full-pipeline.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("full-pipeline")


def run_step(name: str, script: str) -> bool:
    """Exécute un script Python comme sous-processus."""
    logger.info(">>> %s...", name)
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=Path(__file__).resolve().parent.parent,
            check=True,
            capture_output=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.error("Échec de %s (code %d)", name, e.returncode)
        return False


def main():
    logger.info("=" * 50)
    logger.info("  Pipeline complet — Énergie IDF")
    logger.info("=" * 50)

    steps = [
        ("Étape 1/3 : Ingestion", "scripts/ingest.py"),
        ("Étape 2/3 : ETL", "scripts/run_etl.py"),
        ("Étape 3/3 : Dashboard", "scripts/run_dashboard.py"),
    ]

    for name, script in steps:
        if not run_step(name, script):
            logger.error("Pipeline interrompu à : %s", name)
            sys.exit(1)

    logger.info("=" * 50)
    logger.info("  Pipeline terminé avec succès !")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
