"""
Tests unitaires pour Extractor.
"""
import json

import pandas as pd
import pytest

from src.etl.extractor import Extractor


class TestExtractor:
    """Tests pour la classe Extractor."""

    @pytest.fixture
    def data_lake(self, tmp_path):
        """Crée un Data Lake temporaire avec des fichiers de test."""
        lake_dir = tmp_path / "raw"
        lake_dir.mkdir()

        # Fichier JSON (liste de records)
        records = [
            {"date_heure": "2024-01-15T12:00:00", "region": "Île-de-France", "consommation_brute_electricite_mw": 15200},
            {"date_heure": "2024-01-15T11:00:00", "region": "Île-de-France", "consommation_brute_electricite_mw": 14800},
        ]
        json_path = lake_dir / "data_20240115.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(records, f)

        # Fichier CSV
        csv_path = lake_dir / "data_20240115.csv"
        pd.DataFrame(records).to_csv(csv_path, index=False)

        return lake_dir

    @pytest.fixture
    def extractor(self, data_lake):
        return Extractor(data_lake)

    def test_init_valid_dir(self, data_lake):
        ext = Extractor(data_lake)
        assert ext.data_lake_dir == data_lake

    def test_init_invalid_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Extractor(tmp_path / "nonexistent")

    def test_list_files_all(self, extractor):
        files = extractor.list_files()
        assert len(files) == 2

    def test_list_files_json(self, extractor):
        files = extractor.list_files("json")
        assert len(files) == 1
        assert files[0].suffix == ".json"

    def test_list_files_csv(self, extractor):
        files = extractor.list_files("csv")
        assert len(files) == 1

    def test_get_latest_file(self, extractor):
        latest = extractor.get_latest_file("json")
        assert latest is not None
        assert latest.suffix == ".json"

    def test_get_latest_file_none(self, extractor):
        latest = extractor.get_latest_file("parquet")
        assert latest is None

    def test_extract_json(self, extractor, data_lake):
        filepath = data_lake / "data_20240115.json"
        df = extractor.extract_json(filepath)
        assert len(df) == 2
        assert "region" in df.columns

    def test_extract_json_dict_with_results(self, tmp_path):
        """Test extraction d'un JSON au format API (dict avec 'results')."""
        lake = tmp_path / "lake"
        lake.mkdir()
        data = {
            "total_count": 1,
            "results": [{"id": 1, "value": 100}],
        }
        filepath = lake / "api_response.json"
        with open(filepath, "w") as f:
            json.dump(data, f)

        ext = Extractor(lake)
        df = ext.extract_json(filepath)
        assert len(df) == 1
        assert df.iloc[0]["id"] == 1

    def test_extract_json_file_not_found(self, extractor, data_lake):
        with pytest.raises(FileNotFoundError):
            extractor.extract_json(data_lake / "nonexistent.json")

    def test_extract_csv(self, extractor, data_lake):
        filepath = data_lake / "data_20240115.csv"
        df = extractor.extract_csv(filepath)
        assert len(df) == 2

    def test_extract_csv_file_not_found(self, extractor, data_lake):
        with pytest.raises(FileNotFoundError):
            extractor.extract_csv(data_lake / "nonexistent.csv")

    def test_extract_latest_json(self, extractor):
        df = extractor.extract_latest("json")
        assert df is not None
        assert len(df) == 2

    def test_extract_latest_csv(self, extractor):
        df = extractor.extract_latest("csv")
        assert df is not None

    def test_extract_latest_no_file(self, tmp_path):
        lake = tmp_path / "empty_lake"
        lake.mkdir()
        ext = Extractor(lake)
        assert ext.extract_latest("json") is None

    def test_extract_latest_no_matching_files_returns_none(self, extractor):
        """Si aucun fichier ne correspond, retourne None."""
        result = extractor.extract_latest("xml")
        assert result is None

    def test_extract_latest_invalid_extension_with_files(self, tmp_path):
        """Si des fichiers existent mais l'extension n'est pas supportée, lève ValueError."""
        lake = tmp_path / "lake_xml"
        lake.mkdir()
        (lake / "data.xml").write_text("<data/>")

        ext = Extractor(lake)
        with pytest.raises(ValueError, match="Extension non supportée"):
            ext.extract_latest("xml")
