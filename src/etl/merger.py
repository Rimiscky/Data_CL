"""
DataMerger — Fusion des données énergie + météo.
Effectue un merge temporel sur la colonne datetime (nearest hour).
"""
import pandas as pd

from src.utils.logger import get_logger


class DataMerger:
    """Fusionne les données de consommation énergétique et météo."""

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def merge_energy_weather(
        self,
        energy_df: pd.DataFrame,
        weather_df: pd.DataFrame,
        on: str = "datetime",
        tolerance: str = "1h",
    ) -> pd.DataFrame:
        """
        Fusionne énergie et météo sur la colonne datetime (merge_asof).

        Args:
            energy_df: DataFrame de consommation énergétique.
            weather_df: DataFrame météo.
            on: Colonne de jointure temporelle.
            tolerance: Tolérance de jointure (ex: '1h', '30min').

        Returns:
            DataFrame fusionné.
        """
        if energy_df.empty:
            raise ValueError("DataFrame énergie vide")
        if weather_df.empty:
            raise ValueError("DataFrame météo vide")

        energy = energy_df.copy()
        weather = weather_df.copy()

        # Assurer le type datetime UTC
        energy[on] = pd.to_datetime(energy[on], utc=True)
        weather[on] = pd.to_datetime(weather[on], utc=True)

        # Trier par datetime (requis pour merge_asof)
        energy = energy.sort_values(on).reset_index(drop=True)
        weather = weather.sort_values(on).reset_index(drop=True)

        cols_before = set(energy.columns)

        try:
            merged = pd.merge_asof(
                energy,
                weather,
                on=on,
                tolerance=pd.Timedelta(tolerance),
                direction="nearest",
            )
        except Exception as e:
            self.logger.error("Échec merge_asof: %s", e)
            raise

        cols_added = set(merged.columns) - cols_before
        match_rate = merged[list(cols_added)].notna().any(axis=1).mean() * 100

        self.logger.info(
            "Fusion énergie + météo: %d lignes, %d colonnes ajoutées, "
            "%.1f%% de correspondances",
            len(merged), len(cols_added), match_rate,
        )

        return merged

    def add_weather_categories(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute des catégories météo dérivées pour faciliter l'analyse.

        Args:
            df: DataFrame fusionné (énergie + météo).

        Returns:
            DataFrame enrichi avec catégories.
        """
        result = df.copy()

        # Catégorie de température
        if "temperature_2m" in result.columns:
            result["temp_category"] = pd.cut(
                result["temperature_2m"],
                bins=[-float("inf"), 0, 5, 10, 15, 20, 25, float("inf")],
                labels=["gel", "tres_froid", "froid", "frais", "doux", "chaud", "canicule"],
            )

        # Catégorie de vent
        if "wind_speed_10m" in result.columns:
            result["wind_category"] = pd.cut(
                result["wind_speed_10m"],
                bins=[0, 5, 15, 30, float("inf")],
                labels=["calme", "leger", "modere", "fort"],
            )

        # Indicateur de pluie
        if "precipitation" in result.columns:
            result["is_rainy"] = result["precipitation"] > 0.1

        # Confort thermique (température ressentie vs réelle)
        if "apparent_temperature" in result.columns and "temperature_2m" in result.columns:
            result["thermal_gap"] = (
                result["apparent_temperature"] - result["temperature_2m"]
            ).round(1)

        added = [c for c in ["temp_category", "wind_category", "is_rainy", "thermal_gap"]
                 if c in result.columns]
        self.logger.info("Catégories météo ajoutées: %s", added)
        return result
