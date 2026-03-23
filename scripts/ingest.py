"""
Script principal d'ingestion — Jour 1.
Orchestre la récupération des données API + Scraping
et la sauvegarde dans le Data Lake local.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion import ODREClient, WebScraper, DataSaver  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import RAW_API_DIR, RAW_SCRAPING_DIR, RTE_ECO2MIX_URL  # noqa: E402

logger = get_logger("ingest")


def ingest_api(max_records: int = 500) -> Path:
    """Ingestion des données via l'API ODRE."""
    logger.info("=== Démarrage ingestion API ODRE ===")
    saver = DataSaver(RAW_API_DIR)

    with ODREClient() as client:
        # Récupérer les métadonnées du dataset
        info = client.get_dataset_info()
        logger.info("Dataset: %s", info.get("dataset", {}).get("dataset_id", "N/A"))

        # Récupérer les données de consommation
        records = client.fetch_all_consumption(max_records=max_records)

        if not records:
            logger.warning("Aucune donnée récupérée depuis l'API")
            return None

        # Sauvegarder en JSON et CSV
        json_path = saver.save_json(records, prefix="odre_consommation_idf")
        saver.save_csv(records, prefix="odre_consommation_idf")

        logger.info("=== Ingestion API terminée: %d enregistrements ===", len(records))
        return json_path


def ingest_scraping() -> Path:
    """Ingestion des données via scraping."""
    logger.info("=== Démarrage ingestion Scraping ===")
    saver = DataSaver(RAW_SCRAPING_DIR)

    with WebScraper() as scraper:
        soup = scraper.fetch_page(RTE_ECO2MIX_URL)
        if soup is None:
            logger.warning("Page non récupérée")
            return None

        # Extraire les tables
        tables = scraper.extract_tables(soup)
        logger.info("Tables trouvées: %d", len(tables))

        # Extraire les liens vers les données téléchargeables
        data_links = scraper.extract_links(soup, pattern="download")
        logger.info("Liens de téléchargement trouvés: %d", len(data_links))

        result = {
            "source_url": RTE_ECO2MIX_URL,
            "tables": tables,
            "download_links": data_links,
        }

        json_path = saver.save_json(result, prefix="rte_eco2mix_scraping")
        logger.info("=== Ingestion Scraping terminée ===")
        return json_path


def main():
    """Point d'entrée principal."""
    logger.info("========================================")
    logger.info("  Pipeline d'ingestion — Jour 1")
    logger.info("  Consommation énergétique IDF")
    logger.info("========================================")

    try:
        api_path = ingest_api(max_records=500)
        if api_path:
            logger.info("Données API sauvegardées: %s", api_path)
    except Exception as e:
        logger.error("Erreur ingestion API: %s", e)

    try:
        scraping_path = ingest_scraping()
        if scraping_path:
            logger.info("Données scraping sauvegardées: %s", scraping_path)
    except Exception as e:
        logger.error("Erreur ingestion scraping: %s", e)

    logger.info("Pipeline d'ingestion terminé.")


if __name__ == "__main__":
    main()
