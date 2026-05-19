"""
Data Quality Checker — Contrôle qualité des données.
Vérifie la complétude, la cohérence, la fraîcheur et les anomalies.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

from src.utils.logger import get_logger


@dataclass
class QualityRule:
    """Définition d'une règle de qualité."""
    name: str
    description: str
    passed: bool = False
    details: str = ""
    severity: str = "error"  # error, warning, info


@dataclass
class QualityReport:
    """Rapport de qualité complet."""
    dataset_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_rows: int = 0
    total_columns: int = 0
    rules: list = field(default_factory=list)
    score: float = 0.0

    @property
    def passed(self) -> bool:
        # seules les règles "error" bloquent ; les "warning" et "info" sont tolérées
        errors = [r for r in self.rules if not r.passed and r.severity == "error"]
        return len(errors) == 0

    def to_dict(self) -> dict:
        return {
            "dataset_name": self.dataset_name,
            "timestamp": self.timestamp,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "score": round(self.score, 2),
            "passed": self.passed,
            "rules": [
                {
                    "name": r.name,
                    "description": r.description,
                    "passed": bool(r.passed),
                    "details": r.details,
                    "severity": r.severity,
                }
                for r in self.rules
            ],
        }


class DataQualityChecker:
    """Vérifie la qualité des données selon des règles configurables."""

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.logger = get_logger(self.__class__.__name__)

    def run_all_checks(self, df: pd.DataFrame) -> QualityReport:
        """
        Exécute tous les contrôles de qualité sur un DataFrame.

        Args:
            df: DataFrame à vérifier.

        Returns:
            QualityReport avec les résultats.
        """
        report = QualityReport(
            dataset_name=self.dataset_name,
            total_rows=len(df),
            total_columns=len(df.columns),
        )

        report.rules.append(self.check_not_empty(df))
        report.rules.append(self.check_no_full_null_columns(df))
        report.rules.append(self.check_completeness(df, threshold=0.5))  # seuil : 50% de remplissage min
        report.rules.append(self.check_no_duplicates(df))
        report.rules.append(self.check_date_continuity(df))
        report.rules.append(self.check_value_ranges(df))
        report.rules.append(self.check_freshness(df, max_age_days=7))  # données fraîches = < 7 jours

        passed_count = sum(1 for r in report.rules if r.passed)
        # score en pourcentage de règles passées (toutes confondues, indépendamment de la sévérité)
        report.score = (passed_count / len(report.rules)) * 100 if report.rules else 0

        self.logger.info(
            "Qualité [%s]: %.0f%% (%d/%d règles OK)",
            self.dataset_name, report.score, passed_count, len(report.rules),
        )
        return report

    def check_not_empty(self, df: pd.DataFrame) -> QualityRule:
        """Vérifie que le dataset n'est pas vide."""
        rule = QualityRule(
            name="non_empty",
            description="Le dataset contient au moins une ligne",
            severity="error",
        )
        rule.passed = len(df) > 0
        rule.details = f"{len(df)} lignes"
        return rule

    def check_no_full_null_columns(self, df: pd.DataFrame) -> QualityRule:
        """Vérifie qu'aucune colonne n'est entièrement nulle."""
        rule = QualityRule(
            name="no_full_null_columns",
            description="Aucune colonne entièrement nulle",
            severity="warning",
        )
        full_null = [col for col in df.columns if df[col].isna().all()]
        rule.passed = len(full_null) == 0
        rule.details = f"Colonnes nulles: {full_null}" if full_null else "OK"
        return rule

    def check_completeness(
        self, df: pd.DataFrame, threshold: float = 0.5
    ) -> QualityRule:
        """Vérifie que les colonnes clés ont un taux de complétude suffisant."""
        rule = QualityRule(
            name="completeness",
            description=f"Colonnes remplies à >{threshold*100:.0f}%",
            severity="warning",
        )
        completeness = (1 - df.isna().mean())
        low_cols = completeness[completeness < threshold].index.tolist()
        rule.passed = len(low_cols) == 0
        rule.details = (
            f"Colonnes sous le seuil: {low_cols}" if low_cols
            else f"Toutes les colonnes >{threshold*100:.0f}% complètes"
        )
        return rule

    def check_no_duplicates(self, df: pd.DataFrame) -> QualityRule:
        """Vérifie l'absence de doublons complets."""
        rule = QualityRule(
            name="no_duplicates",
            description="Pas de lignes dupliquées",
            severity="warning",
        )
        n_dupes = df.duplicated().sum()
        rule.passed = bool(n_dupes == 0)
        rule.details = f"{n_dupes} doublons" if n_dupes > 0 else "OK"
        return rule

    def check_date_continuity(self, df: pd.DataFrame) -> QualityRule:
        """Vérifie la continuité temporelle (pas de trous)."""
        rule = QualityRule(
            name="date_continuity",
            description="Continuité temporelle des données",
            severity="info",
        )
        if "datetime" not in df.columns:
            rule.passed = True
            rule.details = "Colonne datetime absente, vérification ignorée"
            return rule

        try:
            dates = pd.to_datetime(df["datetime"], utc=True).sort_values()
            diffs = dates.diff().dropna()
            if len(diffs) == 0:
                rule.passed = True
                rule.details = "Pas assez de dates pour vérifier"
                return rule

            median_diff = diffs.median()
            # seuil : un écart > 3× la médiane est considéré comme un trou anormal
            gaps = diffs[diffs > median_diff * 3]
            rule.passed = len(gaps) == 0
            rule.details = (
                f"{len(gaps)} trous détectés (intervalle médian: {median_diff})"
                if len(gaps) > 0
                else f"Continu (intervalle: {median_diff})"
            )
        except Exception as e:
            rule.passed = True
            rule.details = f"Vérification impossible: {e}"

        return rule

    def check_value_ranges(self, df: pd.DataFrame) -> QualityRule:
        """Vérifie que les valeurs numériques sont dans des plages réalistes."""
        rule = QualityRule(
            name="value_ranges",
            description="Valeurs numériques dans des plages réalistes",
            severity="warning",
        )
        issues = []
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            # consommation physiquement non négative : un négatif indique une erreur de mesure
            if (series < 0).any() and "consumption" in col.lower():
                issues.append(f"{col}: valeurs négatives détectées")

        rule.passed = len(issues) == 0
        rule.details = "; ".join(issues) if issues else "OK"
        return rule

    def check_freshness(
        self, df: pd.DataFrame, max_age_days: int = 7
    ) -> QualityRule:
        """Vérifie que les données sont récentes."""
        rule = QualityRule(
            name="freshness",
            description=f"Données de moins de {max_age_days} jours",
            severity="info",
        )
        if "datetime" not in df.columns:
            rule.passed = True
            rule.details = "Colonne datetime absente"
            return rule

        try:
            max_date = pd.to_datetime(df["datetime"], utc=True).max()
            now = pd.Timestamp.now(tz="UTC")  # UTC pour éviter les décalages DST
            age = (now - max_date).days
            rule.passed = age <= max_age_days
            rule.details = f"Dernière donnée: {age} jours"
        except Exception as e:
            rule.passed = True
            rule.details = f"Vérification impossible: {e}"

        return rule

    def save_report(self, report: QualityReport, output_dir: Path) -> Path:
        """Sauvegarde le rapport de qualité en JSON."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"quality_{self.dataset_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        self.logger.info("Rapport qualité sauvegardé: %s", filepath)
        return filepath
