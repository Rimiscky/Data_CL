"""
Tests unitaires pour DataSaver.
"""
import json

import pandas as pd
import pytest

from src.ingestion.data_saver import DataSaver


class TestDataSaver:
    """Tests pour la classe DataSaver."""

    def setup_method(self):
        self.sample_data = [
            {"region": "Île-de-France", "consommation_mw": 15200},
            {"region": "Auvergne-Rhône-Alpes", "consommation_mw": 8900},
        ]

    def test_init_creates_directory(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        assert tmp_data_dir.exists()

    def test_save_json(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        filepath = saver.save_json(self.sample_data, prefix="test")

        assert filepath.exists()
        assert filepath.suffix == ".json"
        assert "test_" in filepath.name

        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == 2
        assert loaded[0]["region"] == "Île-de-France"

    def test_save_json_with_dict(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        filepath = saver.save_json({"key": "value"}, prefix="dict_test")

        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["key"] == "value"

    def test_save_csv(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        filepath = saver.save_csv(self.sample_data, prefix="test")

        assert filepath.exists()
        assert filepath.suffix == ".csv"

        df = pd.read_csv(filepath)
        assert len(df) == 2
        assert "region" in df.columns
        assert "consommation_mw" in df.columns

    def test_save_csv_empty_raises(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        with pytest.raises(ValueError, match="Données vides"):
            saver.save_csv([], prefix="empty")

    def test_save_dataframe_csv(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        df = pd.DataFrame(self.sample_data)
        filepath = saver.save_dataframe(df, prefix="df_test", fmt="csv")

        assert filepath.exists()
        loaded_df = pd.read_csv(filepath)
        assert len(loaded_df) == 2

    def test_save_dataframe_json(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        df = pd.DataFrame(self.sample_data)
        filepath = saver.save_dataframe(df, prefix="df_test", fmt="json")

        assert filepath.exists()
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == 2

    def test_save_dataframe_invalid_format(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        df = pd.DataFrame(self.sample_data)
        with pytest.raises(ValueError, match="Format non supporté"):
            saver.save_dataframe(df, prefix="test", fmt="xml")

    def test_generate_filename_format(self, tmp_data_dir):
        saver = DataSaver(tmp_data_dir)
        filepath = saver._generate_filename("prefix", "json")

        assert filepath.parent == tmp_data_dir
        assert filepath.name.startswith("prefix_")
        assert filepath.suffix == ".json"
