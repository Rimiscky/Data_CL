"""
Script de génération des dashboards — Énergie + Météo.
1. Dashboard énergie classique
2. Dashboard croisé énergie × météo (modulable par période)
3. Rapport de gouvernance (qualité, lignage, catalogue)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

import pandas as pd  # noqa: E402

from src.analysis import DataAnalyzer, DashboardBuilder  # noqa: E402
from src.analysis.cross_dashboard import CrossDashboardBuilder  # noqa: E402
from src.ingestion import MeteoClient, DataSaver  # noqa: E402
from src.etl.merger import DataMerger  # noqa: E402
from src.governance import DataQualityChecker, DataLineageTracker, DataCatalog  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402
from config.settings import (  # noqa: E402
    WAREHOUSE_DIR, BASE_DIR, RAW_METEO_DIR, RAW_RTE_DIR,
    CATALOG_DIR, LINEAGE_DIR, QUALITY_DIR,
)

logger = get_logger("dashboard")

OUTPUT_DIR = BASE_DIR / "output" / "dashboards"


def load_rte_data() -> list:
    """Charge le fichier RTE le plus récent depuis le Data Lake."""
    rte_files = sorted(RAW_RTE_DIR.glob("rte_generation_mix_*.json"))
    if not rte_files:
        logger.warning("Aucun fichier RTE trouvé dans %s", RAW_RTE_DIR)
        return []
    latest = rte_files[-1]
    with open(latest, encoding="utf-8") as f:
        records = json.load(f)
    logger.info("Données RTE chargées: %d filières (%s)", len(records), latest.name)
    return records


def load_warehouse_data() -> pd.DataFrame:
    """Charge les données du warehouse."""
    latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"
    if not latest_csv.exists():
        logger.error("Fichier warehouse introuvable: %s", latest_csv)
        logger.error("Lancez d'abord: python scripts/run_full_pipeline.py")
        sys.exit(1)

    df = pd.read_csv(latest_csv)
    logger.info("Données énergie: %d lignes, %d colonnes", len(df), len(df.columns))
    return df


def fetch_and_merge_meteo(energy_df: pd.DataFrame) -> pd.DataFrame:
    """Récupère la météo et fusionne avec les données énergie."""
    energy_df["datetime"] = pd.to_datetime(energy_df["datetime"], utc=True)
    start = energy_df["datetime"].min().date()
    end = energy_df["datetime"].max().date()

    logger.info("Récupération météo: %s → %s", start, end)

    try:
        with MeteoClient() as client:
            meteo_df = client.fetch_weather_df(start, end)

        if meteo_df.empty:
            logger.warning("Pas de données météo, dashboard énergie seul")
            return energy_df

        # Sauvegarder la météo brute
        saver = DataSaver(RAW_METEO_DIR)
        saver.save_dataframe(meteo_df, prefix="meteo_idf", fmt="csv")

        # Fusionner
        merger = DataMerger()
        merged = merger.merge_energy_weather(energy_df, meteo_df)
        merged = merger.add_weather_categories(merged)

        logger.info(
            "Données fusionnées: %d lignes, %d colonnes",
            len(merged), len(merged.columns),
        )
        return merged

    except Exception as e:
        logger.error("Erreur récupération météo: %s", e)
        logger.warning("Génération du dashboard sans météo")
        return energy_df


def run_governance(df: pd.DataFrame, lineage: DataLineageTracker):
    """Exécute les contrôles de gouvernance."""
    # Qualité
    checker = DataQualityChecker("energy_meteo_idf")
    report = checker.run_all_checks(df)
    checker.save_report(report, QUALITY_DIR)
    logger.info("Qualité: %.0f%% (%s)", report.score, "OK" if report.passed else "WARN")

    # Lignage
    lineage.save(LINEAGE_DIR)

    # Catalogue
    catalog = DataCatalog(CATALOG_DIR)
    catalog.register(
        name="energy_consumption_idf",
        description="Consommation énergétique brute Île-de-France (ODRE)",
        source="API ODRE",
        fmt="csv",
        location=str(WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"),
        df=df,
        tags=["énergie", "idf", "consommation"],
    )
    if "temperature_2m" in df.columns:
        catalog.register(
            name="meteo_idf",
            description="Données météo historiques Île-de-France (Open-Meteo)",
            source="API Open-Meteo",
            fmt="csv",
            location=str(RAW_METEO_DIR),
            df=df[["datetime"] + [c for c in df.columns if c in [
                "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                "precipitation", "cloud_cover",
            ]]],
            tags=["météo", "idf", "température"],
        )
        catalog.register(
            name="energy_meteo_cross",
            description="Données croisées énergie × météo Île-de-France",
            source="Merge energy + meteo",
            fmt="csv",
            location=str(OUTPUT_DIR),
            df=df,
            tags=["croisement", "énergie", "météo", "idf"],
        )
    catalog.save()


def main():
    logger.info("=" * 55)
    logger.info("  Dashboard Énergie × Météo — Île-de-France")
    logger.info("=" * 55)

    # Lignage
    lineage = DataLineageTracker("dashboard_pipeline")

    # 1. Charger les données énergie
    energy_df = load_warehouse_data()
    lineage.add_step(
        "extract_energy", "warehouse/latest.csv", "memory",
        "extract", rows_in=len(energy_df), rows_out=len(energy_df),
    )

    # 2. Récupérer météo + fusionner
    merged_df = fetch_and_merge_meteo(energy_df)
    has_meteo = "temperature_2m" in merged_df.columns
    lineage.add_step(
        "merge_meteo", "API Open-Meteo", "memory",
        "merge", rows_in=len(energy_df), rows_out=len(merged_df),
        columns_added=[c for c in merged_df.columns if c not in energy_df.columns],
    )

    # 3. Dashboard énergie classique
    analyzer = DataAnalyzer(energy_df)
    dashboard = DashboardBuilder(analyzer, output_dir=OUTPUT_DIR)
    dashboard.build_all()

    rte_records = load_rte_data()
    if rte_records:
        dashboard.build_rte_mix(rte_records)

    energy_html = dashboard.export_html()
    logger.info("Dashboard énergie: %s", energy_html)

    # 4. Dashboard croisé (si météo dispo)
    if has_meteo:
        cross_dashboard = CrossDashboardBuilder(merged_df, output_dir=OUTPUT_DIR)
        cross_dashboard.build_all()
        cross_html = cross_dashboard.export_html()
        logger.info("Dashboard croisé: %s", cross_html)
        lineage.add_step(
            "build_cross_dashboard", "memory", str(cross_html),
            "visualize", rows_in=len(merged_df), rows_out=len(merged_df),
        )

    # 5. Gouvernance
    run_governance(merged_df, lineage)

    logger.info("=" * 55)
    logger.info("Dashboards générés dans: %s", OUTPUT_DIR)
    if has_meteo:
        logger.info("  → Énergie : file://%s", energy_html.resolve())
        logger.info("  → Croisé  : file://%s", cross_html.resolve())
    else:
        logger.info("  → Énergie : file://%s", energy_html.resolve())
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
