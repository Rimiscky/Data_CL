"""
Script de génération du dashboard de visualisation — Jour 3.
Lit les données du Data Warehouse et génère un dashboard HTML interactif.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.analysis import DataAnalyzer, DashboardBuilder  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import WAREHOUSE_DIR, BASE_DIR  # noqa: E402

logger = get_logger("dashboard")

OUTPUT_DIR = BASE_DIR / "output" / "dashboards"


def main():
    logger.info("=" * 50)
    logger.info("  Dashboard — Consommation énergétique IDF")
    logger.info("=" * 50)

    # Charger les données du warehouse
    latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"
    if not latest_csv.exists():
        logger.error("Fichier warehouse introuvable: %s", latest_csv)
        logger.error("Lancez d'abord: python scripts/run_full_pipeline.py")
        sys.exit(1)

    try:
        df = pd.read_csv(latest_csv)
        logger.info("Données chargées: %d lignes, %d colonnes", len(df), len(df.columns))
    except Exception as e:
        logger.error("Erreur lecture données: %s", e)
        sys.exit(1)

    # Analyse
    analyzer = DataAnalyzer(df)
    summary = analyzer.summary()
    logger.info("Résumé: %d enregistrements, période %s → %s",
                summary["total_records"],
                summary["date_range"].get("start", "?")[:10],
                summary["date_range"].get("end", "?")[:10])

    elec = summary.get("electricity", {})
    if elec:
        logger.info(
            "Électricité — Moy: %.0f MW | Max: %.0f MW | Min: %.0f MW",
            elec.get("mean_mw", 0), elec.get("max_mw", 0), elec.get("min_mw", 0),
        )

    # Dashboard
    dashboard = DashboardBuilder(analyzer, output_dir=OUTPUT_DIR)
    dashboard.build_all()
    html_path = dashboard.export_html()

    logger.info("=" * 50)
    logger.info("Dashboard généré: %s", html_path)
    logger.info("Ouvrir dans le navigateur: file://%s", html_path.resolve())
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
