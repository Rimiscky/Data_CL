"""
Script principal d'ingestion — Jour 1.
Orchestre la récupération des données API + Scraping
et la sauvegarde dans le Data Lake local.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta  # noqa: E402

import pandas as pd  # noqa: E402

from src.ingestion import ODREClient, MeteoClient, WebScraper, DataSaver  # noqa: E402
from src.ingestion.rte_client import RTEClient  # noqa: E402
from src.ingestion.meteo_france_client import MeteoFranceClient  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import (  # noqa: E402
    RAW_API_DIR,
    RAW_SCRAPING_DIR,
    RAW_METEO_DIR,
    RAW_RTE_DIR,
    RTE_ECO2MIX_URL,
    REGIONS,
)

logger = get_logger("ingest")


def ingest_api(region: str = "idf", max_records: int = 500) -> Path:
    """Ingestion des données via l'API ODRE pour une région."""
    logger.info("=== Démarrage ingestion API ODRE région %s ===", region.upper())
    saver = DataSaver(RAW_API_DIR)

    try:
        with ODREClient.for_region(region) as client:
            # Récupérer les métadonnées du dataset
            info = client.get_dataset_info()
            logger.info("Dataset: %s", info.get("dataset", {}).get("dataset_id", "N/A"))

            # Récupérer les données de consommation
            records = client.fetch_all_consumption(max_records=max_records)

            if not records:
                logger.warning("Aucune donnée récupérée depuis l'API pour %s", region)
                return None

            # Sauvegarder en JSON et CSV
            prefix = f"odre_consommation_{region}"
            json_path = saver.save_json(records, prefix=prefix)
            saver.save_csv(records, prefix=prefix)

            logger.info(
                "=== Ingestion API %s terminée: %d enregistrements ===",
                region.upper(),
                len(records),
            )
            return json_path
    except Exception as e:
        logger.error("Erreur ingestion API pour %s: %s", region, e)
        return None


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
    """Ingestion des données météo via Open-Meteo (multi-régions)."""
    logger.info("=== Démarrage ingestion Météo Open-Meteo ===")
    saver = DataSaver(RAW_METEO_DIR)

    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=90)

    all_dfs = []
    with MeteoClient() as client:
        for region in REGIONS:
            logger.info("Ingestion météo pour région: %s", region)
            try:
                df = client.fetch_weather_df(start_date, end_date, region=region)
                if not df.empty:
                    df["region"] = region
                    all_dfs.append(df)
            except Exception as e:
                logger.error("Erreur ingestion météo région %s: %s", region, e)

    if not all_dfs:
        logger.warning("Aucune donnée météo récupérée")
        return None

    df_combined = pd.concat(all_dfs, ignore_index=True)
    csv_path = saver.save_dataframe(df_combined, prefix="meteo_regions", fmt="csv")
    saver.save_dataframe(df_combined, prefix="meteo_regions", fmt="json")

    logger.info(
        "=== Ingestion Météo terminée: %d enregistrements (%s → %s) ===",
        len(df_combined), start_date, end_date,
    )
    return csv_path


def ingest_rte_realtime(max_records: int = 500) -> Path:
    """Ingestion des données RTE - génération d'électricité."""
    logger.info("=== Démarrage ingestion RTE génération ===")
    saver = DataSaver(RAW_RTE_DIR)

    try:
        with RTEClient() as client:
            # Récupérer les métadonnées
            info = client.get_dataset_info()
            logger.info("Dataset RTE: %s", info.get("dataset", {}).get("dataset_id", "N/A"))

            # Récupérer les données de génération
            records = client.fetch_all_generation(max_records=max_records)

            if not records:
                logger.warning("Aucune donnée RTE récupérée")
                return None

            # Sauvegarder en JSON et CSV
            prefix = "rte_generation_mix"
            json_path = saver.save_json(records, prefix=prefix)
            saver.save_csv(records, prefix=prefix)

            logger.info(
                "=== Ingestion RTE terminée: %d enregistrements ===", len(records)
            )
            return json_path
    except Exception as e:
        logger.error("Erreur ingestion RTE: %s", e)
        return None


def ingest_meteo_france(region: str = "idf", start_date: date = None, end_date: date = None) -> Path:
    """Ingestion des données météo Météo-Concept pour une région."""
    logger.info("=== Démarrage ingestion Météo-Concept région %s ===", region)
    saver = DataSaver(RAW_METEO_DIR)

    if end_date is None:
        end_date = date.today() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    try:
        with MeteoFranceClient() as client:
            df = client.fetch_weather_df(region, start_date, end_date)

            if df.empty:
                logger.warning("Aucune donnée Météo-Concept pour %s", region)
                return None

            prefix = f"meteo_france_{region}"
            csv_path = saver.save_dataframe(df, prefix=prefix, fmt="csv")
            saver.save_dataframe(df, prefix=prefix, fmt="json")

            logger.info(
                "=== Ingestion Météo-Concept %s terminée: %d enregistrements ===",
                region.upper(), len(df),
            )
            return csv_path
    except Exception as e:
        logger.error("Erreur ingestion Météo-Concept %s: %s", region, e)
        return None


def ingest_all_regions(max_records: int = 500) -> list[Path]:
    """Ingère les données pour toutes les régions configurées."""
    logger.info("=== Ingestion multi-régions ===")
    results = []

    for region in REGIONS:
        try:
            path = ingest_api(region=region, max_records=max_records)
            if path:
                results.append(path)
        except Exception as e:
            logger.error("Erreur ingestion région %s: %s", region, e)

    return results


def main():
    """Point d'entrée principal - orchestre tous les ingests."""
    logger.info("========================================")
    logger.info("  Pipeline d'ingestion multi-régions")
    logger.info("  Énergie + Météo + RTE — France")
    logger.info("========================================")

    # Ingestion API ODRE (par défaut IDF)
    try:
        api_path = ingest_api(region="idf", max_records=500)
        if api_path:
            logger.info("Données API IDF sauvegardées: %s", api_path)
    except Exception as e:
        logger.error("Erreur ingestion API: %s", e)

    # Ingestion multi-régions (optionnel)
    try:
        region_paths = ingest_all_regions(max_records=500)
        if region_paths:
            logger.info("Données multi-régions sauvegardées: %d fichiers", len(region_paths))
    except Exception as e:
        logger.error("Erreur ingestion multi-régions: %s", e)

    # Ingestion météo Open-Meteo (multi-régions)
    try:
        meteo_path = ingest_meteo()
        if meteo_path:
            logger.info("Données météo sauvegardées: %s", meteo_path)
    except Exception as e:
        logger.error("Erreur ingestion météo: %s", e)

    # Ingestion RTE - génération d'électricité
    try:
        rte_path = ingest_rte_realtime(max_records=500)
        if rte_path:
            logger.info("Données RTE sauvegardées: %s", rte_path)
    except Exception as e:
        logger.error("Erreur ingestion RTE: %s", e)

    # Ingestion Météo-Concept (optionnel)
    try:
        for region in REGIONS[:1]:  # Commencer par IDF
            meteo_fr_path = ingest_meteo_france(region=region)
            if meteo_fr_path:
                logger.info("Données Météo-Concept %s sauvegardées: %s", region.upper(), meteo_fr_path)
    except Exception as e:
        logger.error("Erreur ingestion Météo-Concept: %s", e)

    # Ingestion par scraping (RTE web)
    try:
        scraping_path = ingest_scraping()
        if scraping_path:
            logger.info("Données scraping sauvegardées: %s", scraping_path)
    except Exception as e:
        logger.error("Erreur ingestion scraping: %s", e)

    logger.info("Pipeline d'ingestion terminé.")


if __name__ == "__main__":
    main()
