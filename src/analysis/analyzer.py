"""
Classe d'analyse de données de consommation énergétique.
Fournit des méthodes d'exploration, statistiques et agrégations
réutilisables pour tout DataFrame de consommation.
"""
from typing import Optional

import pandas as pd
import numpy as np

from src.utils.logger import get_logger


class DataAnalyzer:
    """Analyseur de données de consommation énergétique IDF."""

    def __init__(self, df: pd.DataFrame):
        if df is None or df.empty:
            raise ValueError("Le DataFrame ne peut pas être vide ou None")
        self._df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self._ensure_datetime()

    def _ensure_datetime(self):
        """Convertit la colonne datetime si nécessaire."""
        if "datetime" in self._df.columns:
            self._df["datetime"] = pd.to_datetime(self._df["datetime"], utc=True)

    @property
    def df(self) -> pd.DataFrame:
        """Retourne une copie du DataFrame."""
        return self._df.copy()

    def summary(self) -> dict:
        """
        Résumé statistique complet des données.

        Returns:
            Dict avec shape, période, stats de consommation.
        """
        result = {
            "total_records": len(self._df),
            "columns": list(self._df.columns),
            "date_range": {},
            "electricity": {},
        }

        if "datetime" in self._df.columns:
            result["date_range"] = {
                "start": str(self._df["datetime"].min()),
                "end": str(self._df["datetime"].max()),
                "days_covered": int(self._df["day"].nunique()) if "day" in self._df.columns else 0,
            }

        elec_col = self._detect_elec_column()
        if elec_col:
            series = self._df[elec_col].dropna()
            result["electricity"] = {
                "column": elec_col,
                "mean_mw": round(float(series.mean()), 2),
                "median_mw": round(float(series.median()), 2),
                "std_mw": round(float(series.std()), 2),
                "min_mw": round(float(series.min()), 2),
                "max_mw": round(float(series.max()), 2),
                "total_records": int(series.count()),
            }

        self.logger.info("Résumé généré: %d enregistrements", len(self._df))
        return result

    def hourly_profile(self) -> pd.DataFrame:
        """
        Profil de consommation horaire moyen.

        Returns:
            DataFrame avec mean, std, min, max par heure.
        """
        elec_col = self._detect_elec_column()
        if not elec_col or "hour" not in self._df.columns:
            raise ValueError("Colonnes 'hour' ou consommation électrique manquantes")

        profile = self._df.groupby("hour")[elec_col].agg(
            ["mean", "std", "min", "max", "count"]
        ).round(2)
        profile.columns = ["mean_mw", "std_mw", "min_mw", "max_mw", "count"]
        return profile.reset_index()

    def daily_consumption(self) -> pd.DataFrame:
        """
        Consommation agrégée par jour.

        Returns:
            DataFrame avec total, mean, peak par jour.
        """
        elec_col = self._detect_elec_column()
        if not elec_col or "date" not in self._df.columns:
            raise ValueError("Colonnes 'date' ou consommation électrique manquantes")

        daily = self._df.groupby("date")[elec_col].agg(
            ["sum", "mean", "max", "min", "count"]
        ).round(2)
        daily.columns = ["total_mw", "mean_mw", "peak_mw", "min_mw", "records"]
        return daily.reset_index()

    def weekday_vs_weekend(self) -> pd.DataFrame:
        """
        Comparaison consommation semaine vs weekend.

        Returns:
            DataFrame avec stats par type de jour.
        """
        elec_col = self._detect_elec_column()
        if not elec_col or "is_weekend" not in self._df.columns:
            raise ValueError("Colonnes 'is_weekend' ou consommation électrique manquantes")

        comparison = self._df.groupby("is_weekend")[elec_col].agg(
            ["mean", "std", "min", "max", "count"]
        ).round(2)
        comparison.columns = ["mean_mw", "std_mw", "min_mw", "max_mw", "count"]
        comparison.index = comparison.index.map({True: "Weekend", False: "Semaine"})
        return comparison.reset_index().rename(columns={"is_weekend": "type_jour"})

    def peak_hours(self, top_n: int = 10) -> pd.DataFrame:
        """
        Les N heures de plus forte consommation.

        Args:
            top_n: Nombre de pics à retourner.

        Returns:
            DataFrame trié par consommation décroissante.
        """
        elec_col = self._detect_elec_column()
        if not elec_col:
            raise ValueError("Colonne de consommation électrique manquante")

        cols = ["datetime", "date", "heure", elec_col]
        available_cols = [c for c in cols if c in self._df.columns]
        return (
            self._df[available_cols]
            .nlargest(top_n, elec_col)
            .reset_index(drop=True)
        )

    def day_of_week_profile(self) -> pd.DataFrame:
        """
        Profil de consommation par jour de la semaine.

        Returns:
            DataFrame avec stats par jour (0=Lundi, 6=Dimanche).
        """
        elec_col = self._detect_elec_column()
        if not elec_col or "day_of_week" not in self._df.columns:
            raise ValueError("Colonnes requises manquantes")

        day_names = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
                     4: "Vendredi", 5: "Samedi", 6: "Dimanche"}

        profile = self._df.groupby("day_of_week")[elec_col].agg(
            ["mean", "std", "count"]
        ).round(2)
        profile.columns = ["mean_mw", "std_mw", "count"]
        profile = profile.reset_index()
        profile["day_name"] = profile["day_of_week"].map(day_names)
        return profile

    def detect_anomalies(self, z_threshold: float = 2.5) -> pd.DataFrame:
        """
        Détecte les anomalies par z-score.

        Args:
            z_threshold: Seuil de z-score pour la détection.

        Returns:
            DataFrame des enregistrements anormaux.
        """
        elec_col = self._detect_elec_column()
        if not elec_col:
            raise ValueError("Colonne de consommation électrique manquante")

        series = self._df[elec_col].dropna()
        z_scores = np.abs((series - series.mean()) / series.std())
        mask = z_scores > z_threshold
        anomalies = self._df.loc[mask].copy()
        anomalies["z_score"] = z_scores[mask].round(2)

        self.logger.info(
            "Anomalies détectées: %d/%d (seuil z=%.1f)",
            len(anomalies), len(self._df), z_threshold,
        )
        return anomalies.reset_index(drop=True)

    def _detect_elec_column(self) -> Optional[str]:
        """Détecte automatiquement la colonne de consommation électrique."""
        candidates = [
            "consommation_brute_electricite_rte",
            "elec_consumption_mw",
            "electricity_mw",
        ]
        for col in candidates:
            if col in self._df.columns:
                return col
        return None
