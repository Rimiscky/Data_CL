"""
Data Catalog — Catalogue centralisé des datasets du projet.
Documente chaque source, sa structure, et ses métadonnées.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.logger import get_logger


@dataclass
class DatasetEntry:
    """Entrée du catalogue pour un dataset."""
    name: str
    description: str
    source: str
    format: str
    location: str
    owner: str = "data-team"
    tags: list = field(default_factory=list)
    schema: list = field(default_factory=list)
    row_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "format": self.format,
            "location": self.location,
            "owner": self.owner,
            "tags": self.tags,
            "schema": self.schema,
            "row_count": self.row_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DataCatalog:
    """Catalogue centralisé des datasets."""

    def __init__(self, catalog_dir: Path):
        self.catalog_dir = Path(catalog_dir)
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, DatasetEntry] = {}  # clé = nom unique du dataset
        self.logger = get_logger(self.__class__.__name__)
        self._load_existing()  # réhydrate l'état depuis le fichier JSON si dispo

    def _load_existing(self):
        """Charge le catalogue existant si présent."""
        catalog_file = self.catalog_dir / "catalog.json"
        if catalog_file.exists():
            try:
                with open(catalog_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry_data in data.get("datasets", []):
                    entry = DatasetEntry(**entry_data)
                    self._entries[entry.name] = entry  # l'entrée la plus récente gagne si doublon
                self.logger.info("Catalogue chargé: %d datasets", len(self._entries))
            except Exception as e:
                # catalogue corrompu ou incompatible : on repart d'un état vide plutôt que de planter
                self.logger.warning("Erreur chargement catalogue: %s", e)

    def register(
        self,
        name: str,
        description: str,
        source: str,
        fmt: str,
        location: str,
        df: Optional[pd.DataFrame] = None,
        tags: Optional[list] = None,
        owner: str = "data-team",
    ) -> DatasetEntry:
        """
        Enregistre ou met à jour un dataset dans le catalogue.

        Args:
            name: Nom unique du dataset.
            description: Description du dataset.
            source: Source d'origine (API, scraping, ETL...).
            fmt: Format (csv, json, parquet...).
            location: Chemin ou URL du dataset.
            df: DataFrame optionnel pour extraire le schéma.
            tags: Tags de classification.
            owner: Propriétaire du dataset.

        Returns:
            DatasetEntry créé ou mis à jour.
        """
        schema = []
        row_count = 0
        if df is not None:
            row_count = len(df)
            schema = [
                {
                    "column": col,
                    "dtype": str(df[col].dtype),
                    "nullable": bool(df[col].isna().any()),
                    "unique_count": int(df[col].nunique()),
                    # .dropna() avant iloc[0] pour éviter NaN comme valeur d'exemple
                    "sample": str(df[col].dropna().iloc[0]) if not df[col].dropna().empty else None,
                }
                for col in df.columns
            ]

        entry = DatasetEntry(
            name=name,
            description=description,
            source=source,
            format=fmt,
            location=location,
            owner=owner,
            tags=tags or [],
            schema=schema,
            row_count=row_count,
            updated_at=datetime.now().isoformat(),
        )

        if name in self._entries:
            # mise à jour : on conserve la date de création d'origine
            entry.created_at = self._entries[name].created_at

        self._entries[name] = entry
        self.logger.info("Dataset enregistré: %s (%d lignes, %d colonnes)",
                         name, row_count, len(schema))
        return entry

    def get(self, name: str) -> Optional[DatasetEntry]:
        """Récupère un dataset du catalogue."""
        return self._entries.get(name)

    def list_datasets(self) -> list[str]:
        """Liste tous les datasets du catalogue."""
        return list(self._entries.keys())

    def search(self, tag: str) -> list[DatasetEntry]:
        """Recherche les datasets par tag."""
        return [e for e in self._entries.values() if tag in e.tags]

    def save(self) -> Path:
        """Sauvegarde le catalogue sur disque."""
        filepath = self.catalog_dir / "catalog.json"
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "total_datasets": len(self._entries),
            "datasets": [e.to_dict() for e in self._entries.values()],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.info("Catalogue sauvegardé: %s (%d datasets)", filepath, len(self._entries))
        return filepath

    def to_dataframe(self) -> pd.DataFrame:
        """Exporte le catalogue en DataFrame."""
        return pd.DataFrame([
            {
                "name": e.name,
                "description": e.description,
                "source": e.source,
                "format": e.format,
                "rows": e.row_count,
                "columns": len(e.schema),
                "tags": ", ".join(e.tags),
                "updated_at": e.updated_at,
            }
            for e in self._entries.values()
        ])
