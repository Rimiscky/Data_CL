"""
Script principal d'ingestion — Jour 1.
Orchestre la récupération des données API + Scraping
et la sauvegarde dans le Data Lake local.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402


from src.ingestion import ODREClient, MeteoClient, WebScraper, DataSaver  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import RAW_API_DIR, RAW_SCRAPING_DIR, RAW_METEO_DIR, RTE_ECO2MIX_URL  # noqa: E402

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


def ingest_meteo(start_date: date = None, end_date: date = None) -> Path:
    """Ingestion des données météo via Open-Meteo."""
    logger.info("=== Démarrage ingestion Météo ===")
    saver = DataSaver(RAW_METEO_DIR)

    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=10)

    with MeteoClient() as client:
        df = client.fetch_weather_df(start_date, end_date)

        if df.empty:
            logger.warning("Aucune donnée météo récupérée")
            return None

        csv_path = saver.save_dataframe(df, prefix="meteo_idf", fmt="csv")
        saver.save_dataframe(df, prefix="meteo_idf", fmt="json")

        logger.info(
            "=== Ingestion Météo terminée: %d enregistrements (%s → %s) ===",
            len(df), start_date, end_date,
        )
        return csv_path


def main():
    """Point d'entrée principal."""
    logger.info("========================================")
    logger.info("  Pipeline d'ingestion")
    logger.info("  Énergie + Météo — Île-de-France")
    logger.info("========================================")

    try:
        api_path = ingest_api(max_records=500)
        if api_path:
            logger.info("Données API sauvegardées: %s", api_path)
    except Exception as e:
        logger.error("Erreur ingestion API: %s", e)

    try:
        meteo_path = ingest_meteo()
        if meteo_path:
            logger.info("Données météo sauvegardées: %s", meteo_path)
    except Exception as e:
        logger.error("Erreur ingestion météo: %s", e)

    try:
        scraping_path = ingest_scraping()
        if scraping_path:
            logger.info("Données scraping sauvegardées: %s", scraping_path)
    except Exception as e:
        logger.error("Erreur ingestion scraping: %s", e)

    logger.info("Pipeline d'ingestion terminé.")


if __name__ == "__main__":
    main()
