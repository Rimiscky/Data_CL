"""
Tests unitaires pour DataMerger.
"""
import pytest
import pandas as pd
import numpy as np

from src.etl.merger import DataMerger


@pytest.fixture
def energy_df():
    dates = pd.date_range("2026-02-20", periods=24, freq="h", tz="UTC")
    return pd.DataFrame({
        "datetime": dates,
        "consommation_brute_electricite_rte": np.random.uniform(5000, 12000, 24),
        "region": "Île-de-France",
    })


@pytest.fixture
def weather_df():
    dates = pd.date_range("2026-02-20", periods=24, freq="h", tz="UTC")
    return pd.DataFrame({
        "datetime": dates,
        "temperature_2m": np.random.uniform(-2, 15, 24),
        "relative_humidity_2m": np.random.uniform(60, 95, 24),
        "wind_speed_10m": np.random.uniform(0, 30, 24),
        "precipitation": np.random.uniform(0, 5, 24),
        "apparent_temperature": np.random.uniform(-5, 12, 24),
    })


class TestDataMerger:

    def test_merge_basic(self, energy_df, weather_df):
        merger = DataMerger()
        merged = merger.merge_energy_weather(energy_df, weather_df)

        assert len(merged) == 24
        assert "temperature_2m" in merged.columns
        assert "consommation_brute_electricite_rte" in merged.columns

    def test_merge_adds_weather_columns(self, energy_df, weather_df):
        merger = DataMerger()
        merged = merger.merge_energy_weather(energy_df, weather_df)

        weather_cols = {"temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                        "precipitation", "apparent_temperature"}
        assert weather_cols.issubset(set(merged.columns))

    def test_merge_empty_energy_raises(self, weather_df):
        merger = DataMerger()
        with pytest.raises(ValueError, match="énergie vide"):
            merger.merge_energy_weather(pd.DataFrame(), weather_df)

    def test_merge_empty_weather_raises(self, energy_df):
        merger = DataMerger()
        with pytest.raises(ValueError, match="météo vide"):
            merger.merge_energy_weather(energy_df, pd.DataFrame())

    def test_merge_tolerance(self, energy_df):
        # Météo avec décalage de 30 min
        dates = pd.date_range("2026-02-20 00:30", periods=24, freq="h", tz="UTC")
        weather = pd.DataFrame({
            "datetime": dates,
            "temperature_2m": np.random.uniform(0, 10, 24),
        })
        merger = DataMerger()
        merged = merger.merge_energy_weather(energy_df, weather, tolerance="1h")
        assert merged["temperature_2m"].notna().sum() > 0

    def test_add_weather_categories(self, energy_df, weather_df):
        merger = DataMerger()
        merged = merger.merge_energy_weather(energy_df, weather_df)
        result = merger.add_weather_categories(merged)

        assert "temp_category" in result.columns
        assert "wind_category" in result.columns
        assert "is_rainy" in result.columns
        assert "thermal_gap" in result.columns

    def test_add_weather_categories_missing_cols(self):
        merger = DataMerger()
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = merger.add_weather_categories(df)
        # Ne doit pas crasher, simplement ne rien ajouter
        assert "temp_category" not in result.columns
