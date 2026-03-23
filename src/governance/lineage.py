"""
Data Lineage Tracker — Traçabilité du parcours des données.
Enregistre chaque transformation appliquée : source → destination.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger


@dataclass
class LineageStep:
    """Une étape de transformation dans le lignage."""
    step_name: str
    source: str
    destination: str
    operation: str
    rows_in: int = 0
    rows_out: int = 0
    columns_added: list = field(default_factory=list)
    columns_removed: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "source": self.source,
            "destination": self.destination,
            "operation": self.operation,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "columns_added": self.columns_added,
            "columns_removed": self.columns_removed,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class DataLineageTracker:
    """Suit le lignage des données à travers le pipeline."""

    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self._steps: list[LineageStep] = []
        self._start_time = datetime.now()
        self.logger = get_logger(self.__class__.__name__)

    def add_step(
        self,
        step_name: str,
        source: str,
        destination: str,
        operation: str,
        rows_in: int = 0,
        rows_out: int = 0,
        columns_added: Optional[list] = None,
        columns_removed: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> LineageStep:
        """
        Enregistre une étape de transformation.

        Args:
            step_name: Nom de l'étape.
            source: Source des données.
            destination: Destination des données.
            operation: Type d'opération (extract, transform, load, merge...).
            rows_in: Nombre de lignes en entrée.
            rows_out: Nombre de lignes en sortie.
            columns_added: Colonnes ajoutées.
            columns_removed: Colonnes supprimées.
            metadata: Métadonnées supplémentaires.

        Returns:
            LineageStep enregistré.
        """
        step = LineageStep(
            step_name=step_name,
            source=source,
            destination=destination,
            operation=operation,
            rows_in=rows_in,
            rows_out=rows_out,
            columns_added=columns_added or [],
            columns_removed=columns_removed or [],
            metadata=metadata or {},
        )
        self._steps.append(step)
        self.logger.info(
            "Lignage [%s]: %s → %s (%d→%d lignes)",
            step_name, source, destination, rows_in, rows_out,
        )
        return step

    def get_lineage(self) -> dict:
        """Retourne le lignage complet."""
        return {
            "pipeline_name": self.pipeline_name,
            "start_time": self._start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "total_steps": len(self._steps),
            "steps": [s.to_dict() for s in self._steps],
        }

    def save(self, output_dir: Path) -> Path:
        """Sauvegarde le lignage en JSON."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"lineage_{self.pipeline_name}_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.get_lineage(), f, ensure_ascii=False, indent=2, default=str)
        self.logger.info("Lignage sauvegardé: %s", filepath)
        return filepath

    @property
    def steps(self) -> list[LineageStep]:
        return list(self._steps)
