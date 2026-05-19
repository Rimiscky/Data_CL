"""
Classe réutilisable pour sauvegarder les données dans le Data Lake local.
Supporte JSON et CSV avec horodatage automatique.
"""
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.logger import get_logger


class DataSaver:
    """Sauvegarde les données brutes dans le Data Lake local."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(self.__class__.__name__)

    def _generate_filename(self, prefix: str, extension: str) -> Path:
        """Génère un nom de fichier avec horodatage."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"{prefix}_{timestamp}.{extension}"

    def save_json(self, data: Any, prefix: str = "data") -> Path:
        """
        Sauvegarde les données au format JSON.

        Args:
            data: Données à sauvegarder (dict ou list).
            prefix: Préfixe du nom de fichier.

        Returns:
            Chemin du fichier sauvegardé.
        """
        filepath = self._generate_filename(prefix, "json")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # default=str gère les types non-sérialisables (datetime, numpy) sans planter
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            self.logger.info("JSON sauvegardé: %s", filepath)
            return filepath
        except (IOError, TypeError) as e:
            self.logger.error("Erreur sauvegarde JSON: %s", e)
            raise

    def save_csv(self, data: list[dict], prefix: str = "data") -> Path:
        """
        Sauvegarde une liste de dicts au format CSV.

        Args:
            data: Liste de dictionnaires.
            prefix: Préfixe du nom de fichier.

        Returns:
            Chemin du fichier sauvegardé.
        """
        if not data:
            raise ValueError("Données vides, impossible de sauvegarder en CSV")

        filepath = self._generate_filename(prefix, "csv")
        try:
            fieldnames = list(data[0].keys())  # colonnes inférées depuis le premier enregistrement
            with open(filepath, "w", encoding="utf-8", newline="") as f:  # newline="" requis par csv pour éviter les lignes vides sur Windows
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            self.logger.info("CSV sauvegardé: %s (%d lignes)", filepath, len(data))
            return filepath
        except (IOError, KeyError) as e:
            self.logger.error("Erreur sauvegarde CSV: %s", e)
            raise

    def save_dataframe(self, df: pd.DataFrame, prefix: str = "data", fmt: str = "csv") -> Path:
        """
        Sauvegarde un DataFrame Pandas.

        Args:
            df: DataFrame à sauvegarder.
            prefix: Préfixe du nom de fichier.
            fmt: Format ('csv' ou 'json').

        Returns:
            Chemin du fichier sauvegardé.
        """
        filepath = self._generate_filename(prefix, fmt)
        try:
            if fmt == "csv":
                df.to_csv(filepath, index=False, encoding="utf-8")
            elif fmt == "json":
                df.to_json(filepath, orient="records", force_ascii=False, indent=2)  # orient="records" : une ligne = un objet JSON
            else:
                raise ValueError(f"Format non supporté: {fmt}")

            self.logger.info("DataFrame sauvegardé: %s (%d lignes)", filepath, len(df))
            return filepath
        except Exception as e:
            self.logger.error("Erreur sauvegarde DataFrame: %s", e)
            raise
