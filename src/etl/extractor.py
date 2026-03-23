"""
Extracteur de données depuis le Data Lake local.
Lit les fichiers bruts (JSON, CSV) et les convertit en DataFrame.
"""
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.logger import get_logger


class Extractor:
    """Extraction des données brutes depuis le Data Lake."""

    def __init__(self, data_lake_dir: Path):
        self.data_lake_dir = Path(data_lake_dir)
        self.logger = get_logger(self.__class__.__name__)

        if not self.data_lake_dir.exists():
            raise FileNotFoundError(
                f"Répertoire Data Lake introuvable: {self.data_lake_dir}"
            )

    def list_files(self, extension: str = "*") -> list[Path]:
        """
        Liste les fichiers disponibles dans le Data Lake.

        Args:
            extension: Extension à filtrer ('json', 'csv', '*').

        Returns:
            Liste triée des fichiers (plus récent en premier).
        """
        pattern = f"*.{extension}" if extension != "*" else "*.*"
        files = sorted(
            self.data_lake_dir.glob(pattern),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        self.logger.info(
            "Fichiers trouvés (%s): %d", extension, len(files)
        )
        return files

    def get_latest_file(self, extension: str = "json") -> Optional[Path]:
        """Retourne le fichier le plus récent d'un type donné."""
        files = self.list_files(extension)
        if not files:
            self.logger.warning("Aucun fichier .%s trouvé", extension)
            return None
        return files[0]

    def extract_json(self, filepath: Path) -> pd.DataFrame:
        """
        Extrait les données d'un fichier JSON vers un DataFrame.

        Args:
            filepath: Chemin du fichier JSON.

        Returns:
            DataFrame contenant les données.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            json.JSONDecodeError: Si le JSON est invalide.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Fichier introuvable: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Si c'est un dict avec une clé 'results' (format API ODRE)
                if "results" in data:
                    df = pd.DataFrame(data["results"])
                else:
                    df = pd.DataFrame([data])
            else:
                raise ValueError(f"Format JSON inattendu: {type(data)}")

            self.logger.info(
                "JSON extrait: %s → %d lignes, %d colonnes",
                filepath.name, len(df), len(df.columns),
            )
            return df

        except json.JSONDecodeError as e:
            self.logger.error("JSON invalide dans %s: %s", filepath, e)
            raise
        except Exception as e:
            self.logger.error("Erreur extraction JSON %s: %s", filepath, e)
            raise

    def extract_csv(self, filepath: Path, **kwargs) -> pd.DataFrame:
        """
        Extrait les données d'un fichier CSV vers un DataFrame.

        Args:
            filepath: Chemin du fichier CSV.
            **kwargs: Paramètres supplémentaires pour pd.read_csv.

        Returns:
            DataFrame contenant les données.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Fichier introuvable: {filepath}")

        try:
            df = pd.read_csv(filepath, encoding="utf-8", **kwargs)
            self.logger.info(
                "CSV extrait: %s → %d lignes, %d colonnes",
                filepath.name, len(df), len(df.columns),
            )
            return df
        except Exception as e:
            self.logger.error("Erreur extraction CSV %s: %s", filepath, e)
            raise

    def extract_latest(self, extension: str = "json") -> Optional[pd.DataFrame]:
        """
        Extrait automatiquement le fichier le plus récent.

        Args:
            extension: Type de fichier ('json' ou 'csv').

        Returns:
            DataFrame ou None si aucun fichier trouvé.
        """
        filepath = self.get_latest_file(extension)
        if filepath is None:
            return None

        if extension == "json":
            return self.extract_json(filepath)
        elif extension == "csv":
            return self.extract_csv(filepath)
        else:
            raise ValueError(f"Extension non supportée: {extension}")
