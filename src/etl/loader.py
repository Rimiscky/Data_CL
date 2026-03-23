"""
Loader — Charge les données transformées dans le Data Warehouse local.
Gère le partitionnement par date et les métadonnées.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.logger import get_logger


class Loader:
    """
    Charge les données transformées dans le Data Warehouse.

    Structure de sortie :
        warehouse/
        ├── energy_consumption/
        │   ├── year=2024/
        │   │   ├── month=01/
        │   │   │   └── data.csv
        │   │   └── month=02/
        │   └── latest.csv
        └── metadata/
            └── load_manifest.json
    """

    def __init__(self, warehouse_dir: Path):
        self.warehouse_dir = Path(warehouse_dir)
        self.warehouse_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)

    def load_flat(
        self,
        df: pd.DataFrame,
        table_name: str = "energy_consumption",
        fmt: str = "csv",
    ) -> Path:
        """
        Charge un DataFrame en fichier plat (non partitionné).

        Args:
            df: DataFrame à charger.
            table_name: Nom de la table/dossier.
            fmt: Format de sortie ('csv' ou 'parquet').

        Returns:
            Chemin du fichier chargé.
        """
        if df.empty:
            raise ValueError("DataFrame vide, chargement annulé")

        table_dir = self.warehouse_dir / table_name
        table_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data_{timestamp}.{fmt}"
        filepath = table_dir / filename

        try:
            if fmt == "csv":
                df.to_csv(filepath, index=False, encoding="utf-8")
            elif fmt == "parquet":
                df.to_parquet(filepath, index=False)
            else:
                raise ValueError(f"Format non supporté: {fmt}")

            # Sauvegarder aussi une copie 'latest'
            latest_path = table_dir / f"latest.{fmt}"
            if fmt == "csv":
                df.to_csv(latest_path, index=False, encoding="utf-8")
            elif fmt == "parquet":
                df.to_parquet(latest_path, index=False)

            self.logger.info(
                "Chargé %d lignes → %s", len(df), filepath
            )
            return filepath

        except Exception as e:
            self.logger.error("Erreur chargement: %s", e)
            raise

    def load_partitioned(
        self,
        df: pd.DataFrame,
        table_name: str = "energy_consumption",
        partition_cols: Optional[list[str]] = None,
    ) -> list[Path]:
        """
        Charge les données partitionnées par colonnes (ex: year, month).

        Args:
            df: DataFrame à charger.
            table_name: Nom de la table.
            partition_cols: Colonnes de partitionnement.

        Returns:
            Liste des fichiers créés.
        """
        if df.empty:
            raise ValueError("DataFrame vide, chargement annulé")

        partition_cols = partition_cols or ["year", "month"]

        # Vérifier que les colonnes de partition existent
        missing = [c for c in partition_cols if c not in df.columns]
        if missing:
            raise KeyError(f"Colonnes de partition manquantes: {missing}")

        created_files = []
        table_dir = self.warehouse_dir / table_name

        try:
            for partition_values, group_df in df.groupby(partition_cols):
                if not isinstance(partition_values, tuple):
                    partition_values = (partition_values,)

                # Construire le chemin de partition
                partition_path = table_dir
                for col, val in zip(partition_cols, partition_values):
                    partition_path = partition_path / f"{col}={val}"

                partition_path.mkdir(parents=True, exist_ok=True)
                filepath = partition_path / "data.csv"
                group_df.to_csv(filepath, index=False, encoding="utf-8")

                created_files.append(filepath)
                self.logger.info(
                    "Partition %s: %d lignes", filepath.parent.name, len(group_df)
                )

            self.logger.info(
                "Chargement partitionné: %d partitions créées", len(created_files)
            )
            return created_files

        except Exception as e:
            self.logger.error("Erreur chargement partitionné: %s", e)
            raise

    def save_manifest(
        self,
        df: pd.DataFrame,
        table_name: str,
        source: str = "etl_pipeline",
    ) -> Path:
        """
        Sauvegarde un manifeste de chargement avec les métadonnées.

        Args:
            df: DataFrame chargé.
            table_name: Nom de la table.
            source: Source des données.

        Returns:
            Chemin du fichier manifeste.
        """
        metadata_dir = self.warehouse_dir / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "table_name": table_name,
            "source": source,
            "load_timestamp": datetime.now().isoformat(),
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
            "null_counts": df.isna().sum().to_dict(),
            "numeric_summary": {},
        }

        # Résumé statistique des colonnes numériques
        for col in df.select_dtypes(include="number").columns:
            manifest["numeric_summary"][col] = {
                "min": float(df[col].min()) if not df[col].isna().all() else None,
                "max": float(df[col].max()) if not df[col].isna().all() else None,
                "mean": round(float(df[col].mean()), 2) if not df[col].isna().all() else None,
            }

        filepath = metadata_dir / f"manifest_{table_name}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2, default=str)
            self.logger.info("Manifeste sauvegardé: %s", filepath)
            return filepath
        except Exception as e:
            self.logger.error("Erreur sauvegarde manifeste: %s", e)
            raise
