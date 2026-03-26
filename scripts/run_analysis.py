"""
Script d'orchestration — Lance toutes les analyses et génère un rapport HTML.
Corrélation, clustering, prévisions, et visualisations.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.analysis.clustering import ConsumptionClustering
from src.analysis.correlation_analysis import CorrelationAnalyzer
from src.analysis.forecasting import ConsumptionForecaster
from src.utils.logger import get_logger
from config.settings import WAREHOUSE_DIR, QUALITY_DIR

logger = get_logger("run_analysis")


def load_warehouse_data() -> pd.DataFrame:
    """Charge les données du warehouse."""
    latest_csv = WAREHOUSE_DIR / "energy_consumption_idf" / "latest.csv"

    if not latest_csv.exists():
        logger.warning("Fichier warehouse introuvable: %s", latest_csv)
        return pd.DataFrame()

    df = pd.read_csv(latest_csv)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    logger.info("Warehouse chargé: %d lignes", len(df))
    return df


def run_correlation_analysis(df: pd.DataFrame) -> dict:
    """Lance l'analyse de corrélation."""
    logger.info("=== Analyse de corrélation ===")
    try:
        analyzer = CorrelationAnalyzer(df)
        summary = analyzer.get_summary()
        logger.info("Corrélation OK: %d résultats", len(summary))
        return summary
    except Exception as e:
        logger.error("Erreur corrélation: %s", e)
        return {}


def run_clustering_analysis(df: pd.DataFrame) -> dict:
    """Lance l'analyse de clustering."""
    logger.info("=== Analyse de clustering ===")
    try:
        clusterer = ConsumptionClustering(df)
        clusterer.fit_kmeans(n_clusters=4)

        results = {
            "clusters": clusterer.get_clusters(),
            "profiles": clusterer.get_cluster_profiles(),
            "elbow_curve": clusterer.elbow_curve(max_clusters=8),
        }

        logger.info("Clustering OK: %d clusters", len(results["clusters"]))
        return results
    except Exception as e:
        logger.error("Erreur clustering: %s", e)
        return {}


def run_forecasting_analysis(df: pd.DataFrame) -> dict:
    """Lance les prévisions."""
    logger.info("=== Analyse de prévision ===")
    try:
        forecaster = ConsumptionForecaster(df)

        # ARIMA
        arima_result = forecaster.train_arima(order=(1, 1, 1))
        arima_forecast = None
        if arima_result:
            arima_forecast = forecaster.predict_arima(arima_result, periods=7)

        # Prophet
        prophet_result = forecaster.train_prophet()
        prophet_forecast = None
        if prophet_result:
            prophet_forecast = forecaster.predict_prophet(prophet_result, periods=7)

        results = {
            "arima": {
                "model_info": {k: v for k, v in arima_result.items() if k != "model"},
                "forecast": (
                    arima_forecast.to_dict() if arima_forecast is not None else None
                ),
            },
            "prophet": {
                "forecast": (
                    prophet_forecast.to_dict() if prophet_forecast is not None else None
                ),
            },
        }

        logger.info("Prévisions OK")
        return results
    except Exception as e:
        logger.error("Erreur prévisions: %s", e)
        return {}


def generate_html_report(
    correlation: dict, clustering: dict, forecasting: dict, output_path: Path
) -> Path:
    """
    Génère un rapport HTML avec les résultats de l'analyse.

    Args:
        correlation: Résultats corrélation.
        clustering: Résultats clustering.
        forecasting: Résultats prévisions.
        output_path: Chemin du fichier HTML.

    Returns:
        Chemin du fichier généré.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Rapport d'Analyse Énergétique</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            h1 { color: #333; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
            h2 { color: #0066cc; margin-top: 30px; }
            .section { background: white; padding: 20px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #0066cc; color: white; }
            .metric { display: inline-block; margin: 10px 20px 10px 0; }
            .metric-value { font-size: 24px; font-weight: bold; color: #0066cc; }
            .metric-label { color: #666; font-size: 12px; }
        </style>
    </head>
    <body>
        <h1>📊 Rapport d'Analyse Énergétique × Météo</h1>
        <p><em>Généré le: """ + str(
        pd.Timestamp.now()
    ) + """</em></p>

        <div class="section">
            <h2>🔗 Analyse de Corrélation</h2>
            <pre>""" + json.dumps(
        correlation, indent=2
    ) + """</pre>
        </div>

        <div class="section">
            <h2>🎯 Clustering de Régions</h2>
            <pre>""" + json.dumps(
        clustering, indent=2
    ) + """</pre>
        </div>

        <div class="section">
            <h2>📈 Prévisions</h2>
            <pre>""" + json.dumps(
        forecasting, indent=2
    ) + """</pre>
        </div>

        <hr>
        <p style="color: #999; font-size: 12px;">Rapport généré par le pipeline d'analyse énergétique.</p>
    </body>
    </html>
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info("Rapport HTML généré: %s", output_path)
    return output_path


def main():
    """Point d'entrée principal."""
    logger.info("========================================")
    logger.info("  Analyse Énergétique Complète")
    logger.info("========================================")

    # Charger les données
    df = load_warehouse_data()
    if df.empty:
        logger.error("Aucune donnée à analyser")
        return

    # Lancer les analyses
    correlation = run_correlation_analysis(df)
    clustering = run_clustering_analysis(df)
    forecasting = run_forecasting_analysis(df)

    # Générer le rapport
    output_dir = Path(QUALITY_DIR).parent / "analysis_reports"
    output_path = output_dir / f"analysis_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.html"

    generate_html_report(correlation, clustering, forecasting, output_path)

    logger.info("========================================")
    logger.info("  Analyse terminée")
    logger.info("========================================")


if __name__ == "__main__":
    main()
