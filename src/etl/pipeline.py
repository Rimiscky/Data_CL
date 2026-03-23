"""
Pipeline ETL — Orchestrateur qui enchaîne Extraction, Transformation, Chargement.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.etl.extractor import Extractor
from src.etl.transformer import Transformer
from src.etl.loader import Loader
from src.utils.logger import get_logger


@dataclass
class ETLResult:
    """Résultat d'exécution du pipeline ETL."""
    success: bool
    rows_extracted: int = 0
    rows_loaded: int = 0
    output_path: Optional[Path] = None
    manifest_path: Optional[Path] = None
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"ETLResult({status}) | "
            f"Extracted: {self.rows_extracted} → Loaded: {self.rows_loaded} | "
            f"Duration: {self.duration_seconds:.2f}s"
        )


class ETLPipeline:
    """
    Orchestrateur du pipeline ETL complet.

    Usage:
        pipeline = ETLPipeline(
            data_lake_dir=RAW_API_DIR,
            warehouse_dir=WAREHOUSE_DIR,
        )
        result = pipeline.run()
    """

    def __init__(
        self,
        data_lake_dir: Path,
        warehouse_dir: Path,
        table_name: str = "energy_consumption",
    ):
        self.data_lake_dir = Path(data_lake_dir)
        self.warehouse_dir = Path(warehouse_dir)
        self.table_name = table_name
        self.logger = get_logger(self.__class__.__name__)

    def run(
        self,
        source_extension: str = "json",
        transform_strategy: str = "fill_zero",
        partition: bool = True,
    ) -> ETLResult:
        """
        Exécute le pipeline ETL complet.

        Args:
            source_extension: Format des données source ('json' ou 'csv').
            transform_strategy: Stratégie pour les valeurs manquantes.
            partition: Activer le partitionnement par date.

        Returns:
            ETLResult avec les métriques d'exécution.
        """
        start_time = datetime.now()
        result = ETLResult(success=False)

        try:
            # ── EXTRACT ──────────────────────────────────────
            self.logger.info("═══ ÉTAPE 1/3: EXTRACTION ═══")
            extractor = Extractor(self.data_lake_dir)
            df = extractor.extract_latest(extension=source_extension)

            if df is None or df.empty:
                result.errors.append("Aucune donnée extraite")
                self.logger.error("Pipeline arrêté: aucune donnée")
                return result

            result.rows_extracted = len(df)
            self.logger.info("Extraction OK: %d lignes", result.rows_extracted)

            # ── TRANSFORM ────────────────────────────────────
            self.logger.info("═══ ÉTAPE 2/3: TRANSFORMATION ═══")
            transformer = Transformer(df)
            df_clean = (
                transformer
                .rename_columns()
                .convert_datetime()
                .handle_missing_values(strategy=transform_strategy)
                .enrich_temporal()
                .compute_derived_metrics()
                .validate()
                .get_result()
            )

            if df_clean.empty:
                result.errors.append("DataFrame vide après transformation")
                return result

            self.logger.info("Transformation OK: %d lignes", len(df_clean))

            # ── LOAD ─────────────────────────────────────────
            self.logger.info("═══ ÉTAPE 3/3: CHARGEMENT ═══")
            loader = Loader(self.warehouse_dir)

            # Chargement plat (latest)
            flat_path = loader.load_flat(df_clean, table_name=self.table_name)
            result.output_path = flat_path

            # Chargement partitionné
            if partition and "year" in df_clean.columns and "month" in df_clean.columns:
                loader.load_partitioned(
                    df_clean,
                    table_name=self.table_name,
                    partition_cols=["year", "month"],
                )

            # Manifeste
            result.manifest_path = loader.save_manifest(
                df_clean, table_name=self.table_name
            )

            result.rows_loaded = len(df_clean)
            result.success = True
            self.logger.info("Chargement OK: %d lignes", result.rows_loaded)

        except FileNotFoundError as e:
            result.errors.append(f"Fichier introuvable: {e}")
            self.logger.error("Pipeline FAILED: %s", e)
        except ValueError as e:
            result.errors.append(f"Erreur de valeur: {e}")
            self.logger.error("Pipeline FAILED: %s", e)
        except Exception as e:
            result.errors.append(f"Erreur inattendue: {e}")
            self.logger.error("Pipeline FAILED: %s", e, exc_info=True)
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            result.duration_seconds = duration
            self.logger.info("═══ PIPELINE TERMINÉ: %s ═══", result)

        return result
