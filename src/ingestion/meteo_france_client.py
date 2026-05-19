"""
Client spécialisé pour Météo-Concept API (données régionales français).
Récupère les données météo multi-régions avec plus de précision que Open-Meteo.
"""
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd

from src.ingestion.api_client import APIClient
from config.settings import (
    METEO_FRANCE_BASE_URL,
    METEO_FRANCE_API_KEY,
    REGION_COORDINATES,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


class MeteoFranceClient(APIClient):
    """Client pour Météo-Concept - données météo régionales françaises."""

    def __init__(
        self,
        api_key: str = METEO_FRANCE_API_KEY,
    ):
        super().__init__(
            base_url=METEO_FRANCE_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
        )
        self.api_key = api_key

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """
        Récupère les données météo pour une localisation et période.

        Args:
            latitude: Latitude du point.
            longitude: Longitude du point.
            start_date: Date de début (optionnelle).
            end_date: Date de fin (optionnelle).

        Returns:
            Données JSON de l'API.
        """
        if end_date is None:
            end_date = date.today() - timedelta(days=1)
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        endpoint = "get/history"
        params = {
            "apikey": self.api_key,
            "lat": latitude,
            "lon": longitude,
            "token": self.api_key,  # doublon voulu : certains endpoints Météo-Concept acceptent l'un ou l'autre
        }

        # Note: Météo-Concept peut retourner des données différentes selon l'endpoint
        # Pour cette implémentation, nous supposons un endpoint de type "history"
        try:
            data = self.get(endpoint, params=params)
            self.logger.info(
                "Récupéré données météo pour (%.4f, %.4f)", latitude, longitude
            )
            return data
        except Exception as e:
            self.logger.error("Échec récupération données Météo-Concept: %s", e)
            raise

    def fetch_weather_df(
        self,
        region: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Récupère les données météo pour une région et retourne un DataFrame.

        Args:
            region: Clé région (ex: 'idf', 'provence').
            start_date: Date de début.
            end_date: Date de fin.

        Returns:
            DataFrame avec colonnes: datetime, temperature_2m, relative_humidity_2m, etc.
        """
        if region not in REGION_COORDINATES:
            self.logger.warning("Région inconnue: %s", region)
            return pd.DataFrame()

        latitude, longitude = REGION_COORDINATES[region]

        try:
            data = self.fetch_weather(latitude, longitude, start_date, end_date)
            records = data.get("history", []) or data.get("results", [])  # le nom du champ a changé entre versions de l'API

            if not records:
                self.logger.warning("Aucune donnée météo pour région %s", region)
                return pd.DataFrame()

            # Normaliser les colonnes selon la structure retournée
            df = pd.DataFrame(records)
            df["region"] = region

            # Mapper les colonnes vers le schéma standard si nécessaire
            column_mapping = {
                "time": "datetime",
                "datetime": "datetime",
                "t": "temperature_2m",
                "temperature": "temperature_2m",
                "rh": "relative_humidity_2m",
                "humidity": "relative_humidity_2m",
                "wind": "wind_speed_10m",
                "windspeed": "wind_speed_10m",
                "precip": "precipitation",
                "precipitation": "precipitation",
            }

            for old_col, new_col in column_mapping.items():
                if old_col in df.columns and new_col not in df.columns:
                    df[new_col] = df[old_col]  # garde la colonne source en cas de mapping partiel

            # Convertir datetime en format standard
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")  # errors="coerce" : dates invalides → NaT sans lever d'exception

            self.logger.info(
                "DataFrame météo région %s: %d lignes", region, len(df)
            )
            return df

        except Exception as e:
            self.logger.error("Erreur traitement données Météo-Concept: %s", e)
            return pd.DataFrame()
