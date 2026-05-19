"""
Tests unitaires pour ETLPipeline (test d'intégration léger).
"""
import json

import pandas as pd
import pytest

from src.etl.pipeline import ETLPipeline, ETLResult


class TestETLResult:
    """Tests pour la dataclass ETLResult."""

    def test_default_values(self):
        r = ETLResult(success=False)
        assert r.rows_extracted == 0
        assert r.rows_loaded == 0
        assert r.errors == []

    def test_str_success(self):
        r = ETLResult(success=True, rows_extracted=100, rows_loaded=95, duration_seconds=1.5)
        assert "SUCCESS" in str(r)

    def test_str_failure(self):
        r = ETLResult(success=False)
        assert "FAILED" in str(r)


class TestETLPipeline:
    """Tests d'intégration pour ETLPipeline."""

    @pytest.fixture
    def setup_lake(self, tmp_path):
        """Crée un Data Lake avec des données de test."""
        lake_dir = tmp_path / "raw"
        lake_dir.mkdir()
        warehouse_dir = tmp_path / "warehouse"

        records = [
            {
                "date_heure": "2024-01-15T12:00:00+00:00",
                "region": "Île-de-France",
                "consommation_brute_electricite_rte": 15200,
                "consommation_brute_gaz_totale": 8500,
            },
            {
                "date_heure": "2024-01-15T11:00:00+00:00",
                "region": "Île-de-France",
                "consommation_brute_electricite_rte": 14800,
                "consommation_brute_gaz_totale": 8300,
            },
            {
                "date_heure": "2024-02-01T10:00:00+00:00",
                "region": "Île-de-France",
                "consommation_brute_electricite_rte": 16000,
                "consommation_brute_gaz_totale": 9000,
            },
        ]

        json_path = lake_dir / "odre_data_20240115.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f)

        return lake_dir, warehouse_dir

    def test_full_pipeline_success(self, setup_lake):
        lake_dir, warehouse_dir = setup_lake

        pipeline = ETLPipeline(
            data_lake_dir=lake_dir,
            warehouse_dir=warehouse_dir,
            table_name="test_energy",
        )
        result = pipeline.run(partition=True)

        assert result.success is True
        assert result.rows_extracted == 3
        assert result.rows_loaded == 3
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.manifest_path.exists()
        assert result.duration_seconds > 0
        assert result.errors == []

    def test_pipeline_creates_partitions(self, setup_lake):
        lake_dir, warehouse_dir = setup_lake

        pipeline = ETLPipeline(
            data_lake_dir=lake_dir,
            warehouse_dir=warehouse_dir,
            table_name="test_energy",
        )
        pipeline.run(partition=True)

        # Vérifier les partitions
        jan_path = warehouse_dir / "test_energy" / "year=2024" / "month=1" / "data.csv"
        feb_path = warehouse_dir / "test_energy" / "year=2024" / "month=2" / "data.csv"
        assert jan_path.exists()
        assert feb_path.exists()

    def test_pipeline_no_partition(self, setup_lake):
        lake_dir, warehouse_dir = setup_lake

        pipeline = ETLPipeline(
            data_lake_dir=lake_dir,
            warehouse_dir=warehouse_dir,
        )
        result = pipeline.run(partition=False)
        assert result.success is True

    def test_pipeline_no_data_lake(self, tmp_path):
        pipeline = ETLPipeline(
            data_lake_dir=tmp_path / "nonexistent",
            warehouse_dir=tmp_path / "wh",
        )
        result = pipeline.run()
        assert result.success is False
        assert len(result.errors) > 0

    def test_pipeline_empty_lake(self, tmp_path):
        lake = tmp_path / "empty"
        lake.mkdir()

        pipeline = ETLPipeline(
            data_lake_dir=lake,
            warehouse_dir=tmp_path / "wh",
        )
        result = pipeline.run()
        assert result.success is False

    def test_pipeline_manifest_content(self, setup_lake):
        lake_dir, warehouse_dir = setup_lake

        pipeline = ETLPipeline(
            data_lake_dir=lake_dir,
            warehouse_dir=warehouse_dir,
            table_name="test_energy",
        )
        result = pipeline.run()

        with open(result.manifest_path, "r") as f:
            manifest = json.load(f)

        assert manifest["table_name"] == "test_energy"
        assert manifest["row_count"] == 3
        assert "elec_consumption_mw" in manifest["columns"]
