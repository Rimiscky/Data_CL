"""
Tests unitaires pour Loader.
"""
import json

import pandas as pd
import pytest

from src.etl.loader import Loader


class TestLoader:
    """Tests pour la classe Loader."""

    @pytest.fixture
    def sample_df(self):
        """DataFrame transformé simulé."""
        return pd.DataFrame({
            "datetime": pd.to_datetime(["2024-01-15", "2024-01-16", "2024-02-01"]),
            "region_name": ["Île-de-France"] * 3,
            "elec_consumption_mw": [15200.0, 14800.0, 16000.0],
            "gas_consumption_mw": [8500.0, 8300.0, 9000.0],
            "year": [2024, 2024, 2024],
            "month": [1, 1, 2],
        })

    @pytest.fixture
    def loader(self, tmp_path):
        return Loader(tmp_path / "warehouse")

    # ── Initialisation ─────────────────────────────
    def test_init_creates_dir(self, tmp_path):
        wh_dir = tmp_path / "new_warehouse"
        loader = Loader(wh_dir)
        assert wh_dir.exists()

    # ── load_flat ──────────────────────────────────
    def test_load_flat_csv(self, loader, sample_df):
        path = loader.load_flat(sample_df, table_name="test_table")
        assert path.exists()
        assert path.suffix == ".csv"

        loaded = pd.read_csv(path)
        assert len(loaded) == 3

    def test_load_flat_creates_latest(self, loader, sample_df):
        loader.load_flat(sample_df, table_name="test_table")
        latest = loader.warehouse_dir / "test_table" / "latest.csv"
        assert latest.exists()

    def test_load_flat_empty_raises(self, loader):
        with pytest.raises(ValueError, match="vide"):
            loader.load_flat(pd.DataFrame(), table_name="test")

    def test_load_flat_invalid_format(self, loader, sample_df):
        with pytest.raises(ValueError, match="Format non supporté"):
            loader.load_flat(sample_df, fmt="xml")

    # ── load_partitioned ───────────────────────────
    def test_load_partitioned(self, loader, sample_df):
        paths = loader.load_partitioned(
            sample_df, table_name="test_table", partition_cols=["year", "month"]
        )
        assert len(paths) == 2  # 2 mois distincts

        for p in paths:
            assert p.exists()
            assert p.name == "data.csv"

    def test_load_partitioned_structure(self, loader, sample_df):
        loader.load_partitioned(
            sample_df, table_name="test_table", partition_cols=["year", "month"]
        )
        # Vérifier la structure year=2024/month=1
        expected = loader.warehouse_dir / "test_table" / "year=2024" / "month=1" / "data.csv"
        assert expected.exists()

    def test_load_partitioned_empty_raises(self, loader):
        with pytest.raises(ValueError, match="vide"):
            loader.load_partitioned(pd.DataFrame())

    def test_load_partitioned_missing_col_raises(self, loader, sample_df):
        with pytest.raises(KeyError, match="manquantes"):
            loader.load_partitioned(
                sample_df, partition_cols=["nonexistent"]
            )

    def test_load_partitioned_single_col(self, loader, sample_df):
        paths = loader.load_partitioned(
            sample_df, table_name="test", partition_cols=["year"]
        )
        assert len(paths) == 1  # Un seul year=2024

    # ── save_manifest ──────────────────────────────
    def test_save_manifest(self, loader, sample_df):
        path = loader.save_manifest(sample_df, table_name="test_table")
        assert path.exists()

        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["table_name"] == "test_table"
        assert manifest["row_count"] == 3
        assert manifest["column_count"] == 6
        assert "elec_consumption_mw" in manifest["columns"]

    def test_save_manifest_numeric_summary(self, loader, sample_df):
        path = loader.save_manifest(sample_df, table_name="test")
        with open(path, "r") as f:
            manifest = json.load(f)

        summary = manifest["numeric_summary"]
        assert "elec_consumption_mw" in summary
        assert summary["elec_consumption_mw"]["min"] == 14800.0
        assert summary["elec_consumption_mw"]["max"] == 16000.0

    def test_save_manifest_metadata_dir(self, loader, sample_df):
        loader.save_manifest(sample_df, table_name="test")
        assert (loader.warehouse_dir / "metadata").exists()
