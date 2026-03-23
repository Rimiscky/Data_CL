"""
Tests unitaires pour DataAnalyzer.
"""
import pytest
import pandas as pd
import numpy as np

from src.analysis.analyzer import DataAnalyzer


@pytest.fixture
def sample_df():
    """DataFrame simulant des données du warehouse."""
    dates = pd.date_range("2026-02-20", periods=48, freq="h", tz="UTC")
    return pd.DataFrame({
        "datetime": dates,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "hour": [d.hour for d in dates],
        "day": [d.day for d in dates],
        "day_of_week": [d.weekday() for d in dates],
        "is_weekend": [d.weekday() >= 5 for d in dates],
        "region_name": "Île-de-France",
        "consommation_brute_electricite_rte": [
            8000 + 2000 * np.sin(i * np.pi / 12) + np.random.normal(0, 200)
            for i in range(48)
        ],
    })


class TestDataAnalyzer:
    """Tests pour DataAnalyzer."""

    def test_init_valid(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        assert len(analyzer.df) == 48

    def test_init_empty_raises(self):
        with pytest.raises(ValueError, match="vide"):
            DataAnalyzer(pd.DataFrame())

    def test_init_none_raises(self):
        with pytest.raises(ValueError):
            DataAnalyzer(None)

    def test_init_does_not_mutate(self, sample_df):
        original = sample_df.copy()
        DataAnalyzer(sample_df)
        pd.testing.assert_frame_equal(sample_df, original)

    def test_summary_structure(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        result = analyzer.summary()

        assert "total_records" in result
        assert result["total_records"] == 48
        assert "date_range" in result
        assert "electricity" in result

    def test_summary_electricity_stats(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        elec = analyzer.summary()["electricity"]

        assert elec["column"] == "consommation_brute_electricite_rte"
        assert elec["mean_mw"] > 0
        assert elec["max_mw"] >= elec["mean_mw"]
        assert elec["min_mw"] <= elec["mean_mw"]
        assert elec["total_records"] == 48

    def test_hourly_profile(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        profile = analyzer.hourly_profile()

        assert "hour" in profile.columns
        assert "mean_mw" in profile.columns
        assert len(profile) > 0
        assert profile["count"].sum() == 48

    def test_daily_consumption(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        daily = analyzer.daily_consumption()

        assert "date" in daily.columns
        assert "total_mw" in daily.columns
        assert "peak_mw" in daily.columns
        assert len(daily) > 0

    def test_weekday_vs_weekend(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        comparison = analyzer.weekday_vs_weekend()

        assert "type_jour" in comparison.columns
        assert set(comparison["type_jour"]) <= {"Semaine", "Weekend"}

    def test_peak_hours(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        peaks = analyzer.peak_hours(top_n=5)

        assert len(peaks) == 5
        elec_col = "consommation_brute_electricite_rte"
        values = peaks[elec_col].tolist()
        assert values == sorted(values, reverse=True)

    def test_day_of_week_profile(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        profile = analyzer.day_of_week_profile()

        assert "day_name" in profile.columns
        assert "mean_mw" in profile.columns

    def test_detect_anomalies(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        anomalies = analyzer.detect_anomalies(z_threshold=2.0)

        assert isinstance(anomalies, pd.DataFrame)
        if not anomalies.empty:
            assert "z_score" in anomalies.columns

    def test_detect_elec_column(self, sample_df):
        analyzer = DataAnalyzer(sample_df)
        col = analyzer._detect_elec_column()
        assert col == "consommation_brute_electricite_rte"

    def test_detect_elec_column_missing(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        analyzer = DataAnalyzer(df)
        assert analyzer._detect_elec_column() is None
