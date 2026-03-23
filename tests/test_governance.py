"""
Tests unitaires pour le module Data Governance.
"""
import json
import pytest
import pandas as pd
import numpy as np

from src.governance.quality import DataQualityChecker, QualityReport
from src.governance.lineage import DataLineageTracker
from src.governance.catalog import DataCatalog


# ── DataQualityChecker ───────────────────────────────────

class TestDataQualityChecker:

    @pytest.fixture
    def sample_df(self):
        dates = pd.date_range("2026-02-20", periods=24, freq="h", tz="UTC")
        return pd.DataFrame({
            "datetime": dates,
            "consommation_brute_electricite_rte": np.random.uniform(5000, 12000, 24),
            "region": "Île-de-France",
        })

    def test_run_all_checks(self, sample_df):
        checker = DataQualityChecker("test_dataset")
        report = checker.run_all_checks(sample_df)

        assert isinstance(report, QualityReport)
        assert report.total_rows == 24
        assert report.score > 0
        assert len(report.rules) == 7

    def test_check_not_empty(self, sample_df):
        checker = DataQualityChecker("test")
        rule = checker.check_not_empty(sample_df)
        assert rule.passed is True

    def test_check_not_empty_fails(self):
        checker = DataQualityChecker("test")
        rule = checker.check_not_empty(pd.DataFrame())
        assert rule.passed is False

    def test_check_no_duplicates(self, sample_df):
        checker = DataQualityChecker("test")
        rule = checker.check_no_duplicates(sample_df)
        assert rule.passed is True

    def test_check_no_duplicates_fails(self, sample_df):
        checker = DataQualityChecker("test")
        df_duped = pd.concat([sample_df, sample_df.iloc[:1]])
        rule = checker.check_no_duplicates(df_duped)
        assert rule.passed is False

    def test_check_completeness(self, sample_df):
        checker = DataQualityChecker("test")
        rule = checker.check_completeness(sample_df)
        assert rule.passed is True

    def test_check_completeness_fails(self):
        checker = DataQualityChecker("test")
        df = pd.DataFrame({"a": [1, None, None, None, None]})
        rule = checker.check_completeness(df, threshold=0.5)
        assert rule.passed is False

    def test_report_to_dict(self, sample_df):
        checker = DataQualityChecker("test")
        report = checker.run_all_checks(sample_df)
        d = report.to_dict()

        assert "score" in d
        assert "rules" in d
        assert isinstance(d["rules"], list)

    def test_save_report(self, sample_df, tmp_path):
        checker = DataQualityChecker("test")
        report = checker.run_all_checks(sample_df)
        path = checker.save_report(report, tmp_path)

        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["dataset_name"] == "test"


# ── DataLineageTracker ───────────────────────────────────

class TestDataLineageTracker:

    def test_add_step(self):
        tracker = DataLineageTracker("test_pipeline")
        step = tracker.add_step(
            "extract", "source.csv", "memory",
            "extract", rows_in=100, rows_out=100,
        )
        assert step.step_name == "extract"
        assert len(tracker.steps) == 1

    def test_multiple_steps(self):
        tracker = DataLineageTracker("test")
        tracker.add_step("step1", "a", "b", "extract", 100, 100)
        tracker.add_step("step2", "b", "c", "transform", 100, 95)
        tracker.add_step("step3", "c", "d", "load", 95, 95)

        assert len(tracker.steps) == 3

    def test_get_lineage(self):
        tracker = DataLineageTracker("test")
        tracker.add_step("step1", "a", "b", "extract")
        lineage = tracker.get_lineage()

        assert lineage["pipeline_name"] == "test"
        assert lineage["total_steps"] == 1
        assert len(lineage["steps"]) == 1

    def test_save(self, tmp_path):
        tracker = DataLineageTracker("test")
        tracker.add_step("step1", "a", "b", "extract", 50, 50)
        path = tracker.save(tmp_path)

        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["total_steps"] == 1


# ── DataCatalog ──────────────────────────────────────────

class TestDataCatalog:

    def test_register(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        entry = catalog.register(
            "test_ds", "Test dataset", "api", "csv", "/data/test.csv",
        )
        assert entry.name == "test_ds"
        assert "test_ds" in catalog.list_datasets()

    def test_register_with_df(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        entry = catalog.register(
            "test", "desc", "api", "csv", "/data", df=df,
        )
        assert entry.row_count == 2
        assert len(entry.schema) == 2

    def test_get(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        catalog.register("ds1", "desc", "api", "csv", "/data")
        assert catalog.get("ds1") is not None
        assert catalog.get("nonexistent") is None

    def test_search_by_tag(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        catalog.register("ds1", "d", "api", "csv", "/", tags=["energy"])
        catalog.register("ds2", "d", "api", "csv", "/", tags=["meteo"])
        catalog.register("ds3", "d", "api", "csv", "/", tags=["energy", "meteo"])

        assert len(catalog.search("energy")) == 2
        assert len(catalog.search("meteo")) == 2

    def test_save_and_reload(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        catalog.register("ds1", "desc", "api", "csv", "/data", tags=["test"])
        catalog.save()

        catalog2 = DataCatalog(tmp_path)
        assert "ds1" in catalog2.list_datasets()

    def test_to_dataframe(self, tmp_path):
        catalog = DataCatalog(tmp_path)
        catalog.register("ds1", "desc", "api", "csv", "/data")
        df = catalog.to_dataframe()
        assert len(df) == 1
        assert "name" in df.columns
