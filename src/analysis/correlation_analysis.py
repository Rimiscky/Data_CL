"""
Analyse de corrélation — Étude des relations entre température et consommation d'énergie.
"""
from typing import Dict

import pandas as pd

from src.utils.logger import get_logger


class CorrelationAnalyzer:
    """Analyse les corrélations entre variables météo et consommation."""

    def __init__(self, df: pd.DataFrame):
        """
        Initialise l'analyseur.

        Args:
            df: DataFrame contenant au minimum datetime, consommation et variables météo.

        Raises:
            ValueError: Si le DataFrame est vide.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame vide ou None fourni")

        self.df = df.copy()
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("CorrelationAnalyzer initialisé: %d lignes", len(df))

    def temperature_consumption_corr(self) -> Dict[str, float]:
        """
        Calcule la corrélation de Pearson température ↔ consommation.

        Returns:
            Dict avec corrélation globale et par saison.
        """
        results = {}

        # Corrélation globale
        temp_col = self._find_column(["temperature_2m", "temperature"])
        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )

        if not temp_col or not cons_col:
            self.logger.warning("Colonnes temp ou consommation non trouvées")
            return {}

        global_corr = self.df[[temp_col, cons_col]].corr().iloc[0, 1]
        results["global"] = float(global_corr)
        self.logger.info("Corrélation temp → conso (global): %.3f", global_corr)

        # Corrélation par saison
        if "month" in self.df.columns:
            for month in self.df["month"].unique():
                if pd.notna(month):
                    subset = self.df[self.df["month"] == month]
                    if len(subset) > 2:
                        season_corr = subset[[temp_col, cons_col]].corr().iloc[0, 1]
                        results[f"month_{int(month)}"] = float(season_corr)

        return results

    def humidity_consumption_corr(self) -> Dict[str, float]:
        """Corrélation humidité ↔ consommation."""
        humidity_col = self._find_column(["relative_humidity_2m", "humidity"])
        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )

        if not humidity_col or not cons_col:
            return {}

        corr = self.df[[humidity_col, cons_col]].corr().iloc[0, 1]
        self.logger.info("Corrélation humidité → conso: %.3f", corr)
        return {"global": float(corr)}

    def wind_consumption_corr(self) -> Dict[str, float]:
        """Corrélation vent ↔ consommation."""
        wind_col = self._find_column(["wind_speed_10m", "wind_speed"])
        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )

        if not wind_col or not cons_col:
            return {}

        corr = self.df[[wind_col, cons_col]].corr().iloc[0, 1]
        self.logger.info("Corrélation vent → conso: %.3f", corr)
        return {"global": float(corr)}

    def regional_comparison(self) -> Dict[str, Dict]:
        """
        Compare les profils de consommation par région.

        Returns:
            Dict avec statistiques par région (moy, min, max, std).
        """
        if "region" not in self.df.columns:
            self.logger.warning("Colonne 'region' absente")
            return {}

        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )
        if not cons_col:
            return {}

        results = {}
        for region in self.df["region"].unique():
            if pd.notna(region):
                subset = self.df[self.df["region"] == region][cons_col]
                results[str(region)] = {
                    "mean": float(subset.mean()),
                    "min": float(subset.min()),
                    "max": float(subset.max()),
                    "std": float(subset.std()),
                    "count": int(len(subset)),
                }

        self.logger.info("Comparaison régions: %d régions", len(results))
        return results

    def rte_generation_impact(self) -> Dict[str, float]:
        """
        Calcule l'impact du mix de génération (nucléaire vs renouvelable) sur la consommation.

        Returns:
            Dict avec corrélations génération → consommation.
        """
        results = {}

        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )

        gen_cols = ["nucle", "hydro", "wind", "solar", "thermal"]
        available_gen_cols = [c for c in gen_cols if c in self.df.columns]

        if not cons_col or not available_gen_cols:
            self.logger.warning("Colonnes génération/consommation incomplètes")
            return {}

        for gen_col in available_gen_cols:
            valid_data = self.df[[gen_col, cons_col]].dropna()
            if len(valid_data) > 2:
                corr = valid_data.corr().iloc[0, 1]
                results[gen_col] = float(corr)
                self.logger.info("Corrélation %s → conso: %.3f", gen_col, corr)

        return results

    def hourly_pattern_analysis(self) -> Dict[int, float]:
        """
        Analyse le profil moyen de consommation par heure.

        Returns:
            Dict avec consommation moyenne par heure (0-23).
        """
        if "hour" not in self.df.columns:
            self.logger.warning("Colonne 'hour' absente")
            return {}

        cons_col = self._find_column(
            ["elec_consumption_mw", "consommation_brute_electricite_rte", "total_consumption_mw"]
        )
        if not cons_col:
            return {}

        hourly_avg = self.df.groupby("hour")[cons_col].mean()
        results = {int(h): float(val) for h, val in hourly_avg.items()}
        self.logger.info("Profil horaire calculé: %d heures", len(results))
        return results

    def _find_column(self, candidates: list[str]) -> str:
        """Trouve la première colonne disponible parmi les candidates."""
        for col in candidates:
            if col in self.df.columns:
                return col
        return None

    def get_summary(self) -> Dict:
        """Génère un résumé complet de l'analyse."""
        summary = {
            "temperature_correlation": self.temperature_consumption_corr(),
            "humidity_correlation": self.humidity_consumption_corr(),
            "wind_correlation": self.wind_consumption_corr(),
            "regional_comparison": self.regional_comparison(),
            "generation_impact": self.rte_generation_impact(),
            "hourly_pattern": self.hourly_pattern_analysis(),
        }
        self.logger.info("Analyse de corrélation complétée")
        return summary
