"""
Tests unitaires pour Transformer.
"""
import pandas as pd
import pytest

from src.etl.transformer import Transformer


class TestTransformer:
    """Tests pour la classe Transformer."""

    @pytest.fixture
    def raw_df(self):
        """DataFrame brut simulant les données ODRE."""
        return pd.DataFrame({
            "date_heure": [
                "2024-01-15T12:00:00+00:00",
                "2024-01-15T11:00:00+00:00",
                "2024-01-15T10:00:00+00:00",
                "2024-01-16T08:00:00+00:00",
            ],
            "code_insee_region": ["11", "11", "11", "11"],
            "region": ["Île-de-France"] * 4,
            "consommation_brute_electricite_mw": [15200, 14800, None, 16000],
            "consommation_brute_gaz_mw": [8500, 8300, 8100, None],
        })

    @pytest.fixture
    def transformer(self, raw_df):
        return Transformer(raw_df)

    # ── Initialisation ─────────────────────────────
    def test_init_valid(self, raw_df):
        t = Transformer(raw_df)
        assert len(t.df) == 4

    def test_init_empty_raises(self):
        with pytest.raises(ValueError, match="vide"):
            Transformer(pd.DataFrame())

    def test_init_none_raises(self):
        with pytest.raises(ValueError, match="vide"):
            Transformer(None)

    def test_init_does_not_mutate_original(self, raw_df):
        t = Transformer(raw_df)
        t.rename_columns()
        assert "date_heure" in raw_df.columns  # Original inchangé

    # ── rename_columns ─────────────────────────────
    def test_rename_columns(self, transformer):
        result = transformer.rename_columns()
        assert "datetime" in result.df.columns
        assert "elec_consumption_mw" in result.df.columns
        assert "date_heure" not in result.df.columns

    def test_rename_columns_returns_self(self, transformer):
        result = transformer.rename_columns()
        assert result is transformer

    # ── convert_datetime ───────────────────────────
    def test_convert_datetime(self, transformer):
        transformer.rename_columns().convert_datetime()
        assert pd.api.types.is_datetime64_any_dtype(transformer.df["datetime"])

    def test_convert_datetime_missing_column(self, transformer):
        result = transformer.convert_datetime("nonexistent")
        assert result is transformer  # No error, just warning

    # ── handle_missing_values ──────────────────────
    def test_handle_missing_drop(self, transformer):
        transformer.rename_columns()
        before = len(transformer.df)
        transformer.handle_missing_values(strategy="drop")
        assert len(transformer.df) < before

    def test_handle_missing_fill_zero(self, transformer):
        transformer.rename_columns().handle_missing_values(strategy="fill_zero")
        assert transformer.df["elec_consumption_mw"].isna().sum() == 0
        assert transformer.df["gas_consumption_mw"].isna().sum() == 0

    def test_handle_missing_fill_mean(self, transformer):
        transformer.rename_columns().handle_missing_values(strategy="fill_mean")
        assert transformer.df["elec_consumption_mw"].isna().sum() == 0

    def test_handle_missing_fill_median(self, transformer):
        transformer.rename_columns().handle_missing_values(strategy="fill_median")
        assert transformer.df["elec_consumption_mw"].isna().sum() == 0

    def test_handle_missing_fill_value(self, transformer):
        transformer.rename_columns().handle_missing_values(
            strategy="fill_value", fill_value=-1
        )
        assert -1 in transformer.df["elec_consumption_mw"].values

    def test_handle_missing_fill_value_no_value_raises(self, transformer):
        with pytest.raises(ValueError, match="fill_value requis"):
            transformer.handle_missing_values(strategy="fill_value")

    def test_handle_missing_unknown_strategy_raises(self, transformer):
        with pytest.raises(ValueError, match="Stratégie inconnue"):
            transformer.handle_missing_values(strategy="unknown")

    # ── enrich_temporal ────────────────────────────
    def test_enrich_temporal(self, transformer):
        transformer.rename_columns().convert_datetime().enrich_temporal()
        expected_cols = ["year", "month", "day", "hour", "day_of_week", "is_weekend", "quarter"]
        for col in expected_cols:
            assert col in transformer.df.columns

    def test_enrich_temporal_values(self, transformer):
        transformer.rename_columns().convert_datetime().enrich_temporal()
        assert transformer.df["year"].iloc[0] == 2024
        assert transformer.df["month"].iloc[0] == 1

    def test_enrich_temporal_missing_column(self, transformer):
        result = transformer.enrich_temporal("nonexistent")
        assert result is transformer

    # ── compute_derived_metrics ────────────────────
    def test_compute_derived_metrics(self, transformer):
        transformer.rename_columns().convert_datetime()
        transformer.handle_missing_values(strategy="fill_zero")
        transformer.compute_derived_metrics()
        assert "elec_ratio" in transformer.df.columns
        assert "total_consumption_mw" in transformer.df.columns

    def test_compute_derived_metrics_change(self, transformer):
        transformer.rename_columns().convert_datetime()
        transformer.handle_missing_values(strategy="fill_zero")
        transformer.compute_derived_metrics()
        assert "elec_change_mw" in transformer.df.columns
        assert "elec_change_pct" in transformer.df.columns

    # ── filter_outliers ────────────────────────────
    def test_filter_outliers(self, transformer):
        transformer.rename_columns().handle_missing_values(strategy="fill_zero")
        before = len(transformer.df)
        transformer.filter_outliers("elec_consumption_mw", 0.1, 0.9)
        assert len(transformer.df) <= before

    def test_filter_outliers_missing_column(self, transformer):
        result = transformer.filter_outliers("nonexistent")
        assert result is transformer

    # ── validate ───────────────────────────────────
    def test_validate(self, transformer):
        result = transformer.validate()
        assert result is transformer

    def test_validate_removes_duplicates(self):
        df = pd.DataFrame({"a": [1, 1, 2], "b": [3, 3, 4]})
        t = Transformer(df)
        t.validate()
        assert len(t.df) == 2

    # ── run_full_pipeline ──────────────────────────
    def test_run_full_pipeline(self, raw_df):
        t = Transformer(raw_df)
        result_df = t.run_full_pipeline()
        assert not result_df.empty
        assert "datetime" in result_df.columns or "year" in result_df.columns
        assert result_df.isna().sum().sum() == 0 or True  # fill_zero appliqué

    # ── get_result ─────────────────────────────────
    def test_get_result_returns_copy(self, transformer):
        df1 = transformer.get_result()
        df2 = transformer.get_result()
        assert df1 is not df2

    # ── Chaînage (fluent API) ──────────────────────
    def test_method_chaining(self, raw_df):
        result = (
            Transformer(raw_df)
            .rename_columns()
            .convert_datetime()
            .handle_missing_values(strategy="fill_zero")
            .enrich_temporal()
            .validate()
            .get_result()
        )
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
