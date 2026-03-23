"""
Tests unitaires pour MeteoClient.
"""
import pytest
from datetime import date
from unittest.mock import patch

import pandas as pd

from src.ingestion.meteo_client import MeteoClient


class TestMeteoClient:

    def setup_method(self):
        self.client = MeteoClient(latitude=48.85, longitude=2.35)
        self.client.retry_delay = 0

    def teardown_method(self):
        self.client.close()

    def test_initialization(self):
        assert self.client.latitude == 48.85
        assert self.client.longitude == 2.35

    @patch.object(MeteoClient, "get")
    def test_fetch_weather(self, mock_get):
        mock_get.return_value = {
            "hourly": {
                "time": ["2026-02-20T00:00", "2026-02-20T01:00"],
                "temperature_2m": [5.2, 4.8],
                "relative_humidity_2m": [85, 87],
            }
        }

        result = self.client.fetch_weather(date(2026, 2, 20), date(2026, 2, 21))
        assert "hourly" in result
        assert len(result["hourly"]["time"]) == 2

    @patch.object(MeteoClient, "get")
    def test_fetch_weather_df(self, mock_get):
        mock_get.return_value = {
            "hourly": {
                "time": ["2026-02-20T00:00", "2026-02-20T01:00", "2026-02-20T02:00"],
                "temperature_2m": [5.2, 4.8, 4.5],
                "wind_speed_10m": [10.0, 12.0, 8.0],
            }
        }

        df = self.client.fetch_weather_df(date(2026, 2, 20), date(2026, 2, 21))
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "datetime" in df.columns
        assert "temperature_2m" in df.columns
        assert df["datetime"].dt.tz is not None  # UTC

    @patch.object(MeteoClient, "get")
    def test_fetch_weather_df_empty(self, mock_get):
        mock_get.return_value = {"hourly": {}}

        df = self.client.fetch_weather_df(date(2026, 2, 20), date(2026, 2, 21))
        assert df.empty

    @patch.object(MeteoClient, "get")
    def test_fetch_weather_error(self, mock_get):
        mock_get.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            self.client.fetch_weather(date(2026, 2, 20), date(2026, 2, 21))
