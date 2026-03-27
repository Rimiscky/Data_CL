"""
Exporter Prometheus — Exposes pipeline metrics.
Métriques: durée de pipeline, lignes ingérées, score qualité, erreurs.
"""
import time
from pathlib import Path
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

from src.utils.logger import get_logger


class PipelineMetrics:
    """Collecteur de métriques Prometheus pour le pipeline."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialise les métriques.

        Args:
            registry: CollectorRegistry optionnel (défaut: REGISTRY globale).
        """
        self.registry = registry
        self.logger = get_logger(self.__class__.__name__)

        # Métriques de durée
        self.pipeline_duration = Histogram(
            "pipeline_duration_seconds",
            "Durée d'exécution du pipeline en secondes",
            buckets=(10, 30, 60, 120, 300, 600),
            registry=self.registry,
        )

        # Métriques de volume de données ingérées
        self.ingested_rows_total = Counter(
            "ingested_rows_total",
            "Nombre total de lignes ingérées",
            labelnames=["source", "region"],
            registry=self.registry,
        )

        # Métriques de qualité des données
        self.data_quality_score = Gauge(
            "data_quality_score",
            "Score de qualité des données (%)",
            labelnames=["dataset"],
            registry=self.registry,
        )

        # Métriques d'erreurs
        self.task_failures_total = Counter(
            "task_failures_total",
            "Nombre total d'échecs de tâche",
            labelnames=["task_id", "error_type"],
            registry=self.registry,
        )

        # Métriques de fraîcheur des données
        self.data_freshness_seconds = Gauge(
            "data_freshness_seconds",
            "Âge des données en secondes (depuis last update)",
            labelnames=["source"],
            registry=self.registry,
        )

        # Métriques de disponibilité
        self.pipeline_runs_total = Counter(
            "pipeline_runs_total",
            "Nombre total d'exécutions du pipeline",
            labelnames=["status"],  # success, failed
            registry=self.registry,
        )

    def record_ingestion(self, source: str, region: str, row_count: int):
        """Enregistre une ingestion de données."""
        self.ingested_rows_total.labels(source=source, region=region).inc(row_count)
        self.logger.info(
            "Métrique: %d lignes ingérées de %s (région: %s)",
            row_count, source, region,
        )

    def record_quality_score(self, dataset: str, score: float):
        """Enregistre le score de qualité."""
        self.data_quality_score.labels(dataset=dataset).set(score)
        self.logger.info("Métrique: Score qualité %s = %.1f%%", dataset, score)

    def record_failure(self, task_id: str, error_type: str):
        """Enregistre une erreur de tâche."""
        self.task_failures_total.labels(task_id=task_id, error_type=error_type).inc()
        self.logger.warning("Métrique: Échec tâche %s (%s)", task_id, error_type)

    def record_data_freshness(self, source: str, age_seconds: int):
        """Enregistre l'âge des données (fraîcheur)."""
        self.data_freshness_seconds.labels(source=source).set(age_seconds)
        self.logger.info("Métrique: Fraîcheur %s = %d secondes", source, age_seconds)

    def record_pipeline_run(self, status: str):
        """Enregistre l'exécution du pipeline."""
        self.pipeline_runs_total.labels(status=status).inc()
        self.logger.info("Métrique: Exécution pipeline = %s", status)

    @staticmethod
    def context_duration(metrics: "PipelineMetrics"):
        """Context manager pour mesurer la durée."""
        class DurationContext:
            def __init__(self, mets):
                self.metrics = mets
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start_time
                self.metrics.pipeline_duration.observe(duration)
                self.metrics.logger.info(
                    "Pipeline durée: %.1f secondes", duration
                )

        return DurationContext(metrics)


def get_exporter_port() -> int:
    """Retourne le port Prometheus (défaut: 9091)."""
    import os
    return int(os.getenv("PROMETHEUS_EXPORTER_PORT", 9091))


def start_http_server(port: int = None, registry: Optional[CollectorRegistry] = None):
    """
    Démarre le serveur HTTP Prometheus.

    Args:
        port: Port d'écoute (défaut: 9091).
        registry: Registre de métriques optionnel.
    """
    if port is None:
        port = get_exporter_port()

    try:
        from prometheus_client import start_http_server as prom_start
        prom_start(port=port, registry=registry)
        logger = get_logger("prometheus_exporter")
        logger.info("Serveur Prometheus démarré sur port %d", port)
    except ImportError:
        logger = get_logger("prometheus_exporter")
        logger.warning("prometheus_client non installé: pip install prometheus-client")
    except Exception as e:
        logger = get_logger("prometheus_exporter")
        logger.error("Erreur démarrage serveur Prometheus: %s", e)


def export_metrics_file(metrics: PipelineMetrics, filepath: Path):
    """
    Exporte les métriques au format Prometheus texte.

    Args:
        metrics: Instance PipelineMetrics.
        filepath: Chemin du fichier de sortie.
    """
    try:
        from prometheus_client import generate_latest

        output = generate_latest(metrics.registry)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "wb") as f:
            f.write(output)

        logger = get_logger("prometheus_exporter")
        logger.info("Métriques exportées: %s", filepath)
    except Exception as e:
        logger = get_logger("prometheus_exporter")
        logger.error("Erreur export métriques: %s", e)
