"""
Tests unitaires pour CrossDashboardBuilder.
"""
import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.analysis.cross_dashboard import CrossDashboardBuilder


@pytest.fixture
def merged_df():
    """DataFrame simulant des données fusionnées énergie + météo."""
    dates = pd.date_range("2026-02-20", periods=48, freq="h", tz="UTC")
    return pd.DataFrame({
        "datetime": dates,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "hour": [d.hour for d in dates],
        "day_of_week": [d.weekday() for d in dates],
        "is_weekend": [d.weekday() >= 5 for d in dates],
        "consommation_brute_electricite_rte": [
            8000 + 2000 * np.sin(i * np.pi / 12) for i in range(48)
        ],
        "temperature_2m": [5 + 5 * np.sin(i * np.pi / 12) for i in range(48)],
        "apparent_temperature": [3 + 5 * np.sin(i * np.pi / 12) for i in range(48)],
        "relative_humidity_2m": np.random.uniform(60, 95, 48),
        "wind_speed_10m": np.random.uniform(0, 25, 48),
        "precipitation": np.random.choice([0, 0, 0, 0.5, 1.0, 2.0], 48),
        "cloud_cover": np.random.uniform(0, 100, 48),
        "surface_pressure": np.random.uniform(1010, 1025, 48),
        "temp_category": pd.Categorical(
            np.random.choice(["froid", "frais", "doux"], 48),
            categories=["gel", "tres_froid", "froid", "frais", "doux", "chaud", "canicule"],
        ),
        "wind_category": pd.Categorical(
            np.random.choice(["calme", "leger", "modere"], 48),
            categories=["calme", "leger", "modere", "fort"],
        ),
        "is_rainy": np.random.choice([True, False], 48),
        "thermal_gap": np.random.uniform(-3, 0, 48),
    })


class TestCrossDashboardBuilder:

    def test_init(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        assert len(db.df) == 48

    def test_init_empty_raises(self, tmp_path):
        with pytest.raises(ValueError):
            CrossDashboardBuilder(pd.DataFrame(), output_dir=tmp_path)

    def test_build_energy_vs_temperature(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_energy_vs_temperature()
        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2

    def test_build_scatter_temp_consumption(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_scatter_temp_consumption()
        assert isinstance(fig, go.Figure)

    def test_build_weather_impact_bars(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_weather_impact_bars()
        assert isinstance(fig, go.Figure)

    def test_build_multivar_heatmap(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_multivar_heatmap()
        assert isinstance(fig, go.Figure)

    def test_build_wind_rain_analysis(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_wind_rain_analysis()
        assert isinstance(fig, go.Figure)

    def test_build_daily_overview(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        fig = db.build_daily_overview()
        assert isinstance(fig, go.Figure)

    def test_build_all(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        figures = db.build_all()
        assert len(figures) == 6

    def test_export_html(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        html_path = db.export_html("test_cross.html")

        assert html_path.exists()
        content = html_path.read_text()
        assert "Énergie" in content
        assert "Météo" in content or "teo" in content
        assert "cross_chart_0" in content
        assert "applyFilters" in content  # Filtre JS

    def test_export_html_auto_builds(self, merged_df, tmp_path):
        db = CrossDashboardBuilder(merged_df, output_dir=tmp_path)
        html_path = db.export_html()
        assert html_path.exists()
        assert len(db._figures) == 6

    def test_missing_meteo_columns(self, tmp_path):
        """Dashboard sans colonnes météo ne crash pas."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2026-02-20", periods=10, freq="h", tz="UTC"),
            "consommation_brute_electricite_rte": range(10),
        })
        db = CrossDashboardBuilder(df, output_dir=tmp_path)
        fig = db.build_energy_vs_temperature()
        assert isinstance(fig, go.Figure)  # empty_figure
