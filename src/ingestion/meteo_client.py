"""
Client API Open-Meteo — Données météo historiques horaires.
Récupère température, humidité, vent, précipitations pour l'Île-de-France.
Gratuit, sans clé API.
"""
from datetime import date
from typing import Optional

import pandas as pd

from src.ingestion.api_client import APIClient
from src.utils.logger import get_logger
from config.settings import (
    OPENMETEO_BASE_URL,
    IDF_LATITUDE,
    IDF_LONGITUDE,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


class MeteoClient(APIClient):
    """Client pour l'API Open-Meteo — météo historique Île-de-France."""

    # Variables météo horaires disponibles
    HOURLY_VARIABLES = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "wind_speed_10m",
        "cloud_cover",
        "surface_pressure",
    ]

    def __init__(
        self,
        latitude: float = IDF_LATITUDE,
        longitude: float = IDF_LONGITUDE,
    ):
        super().__init__(
            base_url=OPENMETEO_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
        )
        self.latitude = latitude
        self.longitude = longitude
        self.logger = get_logger(self.__class__.__name__)

    def fetch_weather(
        self,
        start_date: date,
        end_date: date,
        variables: Optional[list[str]] = None,
    ) -> dict:
        """
        Récupère les données météo historiques horaires.

        Args:
            start_date: Date de début.
            end_date: Date de fin.
            variables: Liste des variables (défaut: toutes).

        Returns:
            Données JSON brutes de l'API.
        """
        vars_list = variables or self.HOURLY_VARIABLES
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(vars_list),
            "timezone": "UTC",
        }

        try:
            data = self.get("archive", params=params)
            n_hours = len(data.get("hourly", {}).get("time", []))
            self.logger.info(
                "Météo récupérée: %s → %s (%d heures, %d variables)",
                start_date, end_date, n_hours, len(vars_list),
            )
            return data
        except Exception as e:
            self.logger.error("Échec récupération météo: %s", e)
            raise

    def fetch_weather_df(
        self,
        start_date: date,
        end_date: date,
        variables: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo et retourne un DataFrame prêt à fusionner.

        Args:
            start_date: Date de début.
            end_date: Date de fin.
            variables: Liste des variables.

        Returns:
            DataFrame avec colonne 'datetime' en UTC.
        """
        data = self.fetch_weather(start_date, end_date, variables)
        hourly = data.get("hourly", {})

        if not hourly or "time" not in hourly:
            self.logger.warning("Pas de données horaires dans la réponse")
            return pd.DataFrame()

        df = pd.DataFrame(hourly)
        df.rename(columns={"time": "datetime"}, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

        self.logger.info("DataFrame météo: %d lignes, %d colonnes", len(df), len(df.columns))
        return df
