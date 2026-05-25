"""
Tests unitaires pour DashboardBuilder.
"""
import pytest
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.analysis.analyzer import DataAnalyzer
from src.analysis.dashboard import DashboardBuilder


@pytest.fixture
def analyzer():
    """Crée un DataAnalyzer avec des données simulées."""
    dates = pd.date_range("2026-02-20", periods=48, freq="h", tz="UTC")
    df = pd.DataFrame({
        "datetime": dates,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "hour": [d.hour for d in dates],
        "day": [d.day for d in dates],
        "day_of_week": [d.weekday() for d in dates],
        "is_weekend": [d.weekday() >= 5 for d in dates],
        "region_name": "Île-de-France",
        "consommation_brute_electricite_rte": [
            8000 + 2000 * np.sin(i * np.pi / 12) for i in range(48)
        ],
    })
    return DataAnalyzer(df)


class TestDashboardBuilder:
    """Tests pour DashboardBuilder."""

    def test_init(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path / "dash")
        assert (tmp_path / "dash").exists()

    def test_build_hourly_profile(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_hourly_profile()

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_build_daily_consumption(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_daily_consumption()

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 1

    def test_build_weekday_comparison(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_weekday_comparison()

        assert isinstance(fig, go.Figure)

    def test_build_day_of_week_profile(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_day_of_week_profile()

        assert isinstance(fig, go.Figure)

    def test_build_heatmap(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_heatmap()

        assert isinstance(fig, go.Figure)

    def test_build_anomalies_chart(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db.build_anomalies_chart()

        assert isinstance(fig, go.Figure)

    def test_build_all(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        figures = db.build_all()

        assert isinstance(figures, dict)
        assert len(figures) == 6
        expected_keys = {
            "hourly_profile", "daily_consumption", "weekday_comparison",
            "day_of_week", "heatmap", "anomalies",
        }
        assert set(figures.keys()) == expected_keys

    def test_export_html(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        html_path = db.export_html("test_dashboard.html")

        assert html_path.exists()
        assert html_path.suffix == ".html"

        content = html_path.read_text(encoding="utf-8")
        assert "Île-de-France" in content
        assert "plotly-2.27.0" in content
        assert "c-ts" in content

    def test_export_html_builds_if_empty(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        # Sans appeler build_all() d'abord — le HTML est généré depuis les données brutes
        html_path = db.export_html()

        assert html_path.exists()
        assert html_path.stat().st_size > 0

    def test_empty_figure(self, analyzer, tmp_path):
        db = DashboardBuilder(analyzer, output_dir=tmp_path)
        fig = db._empty_figure("Test message")

        assert isinstance(fig, go.Figure)

    def test_with_missing_columns(self, tmp_path):
        """Dashboard avec données incomplètes ne crash pas."""
        df = pd.DataFrame({
            "consommation_brute_electricite_rte": [100, 200, 300],
            "other_col": ["a", "b", "c"],
        })
        analyzer = DataAnalyzer(df)
        db = DashboardBuilder(analyzer, output_dir=tmp_path)

        # Ne doit pas lever d'exception
        fig = db.build_hourly_profile()
        assert isinstance(fig, go.Figure)
