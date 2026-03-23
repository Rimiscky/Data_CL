"""
Tests unitaires pour ODREClient.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.ingestion.odre_client import ODREClient


class TestODREClient:
    """Tests pour la classe ODREClient."""

    def setup_method(self):
        self.client = ODREClient(
            dataset="test-dataset",
            region="Île-de-France",
            rows_limit=10,
        )
        self.client.retry_delay = 0

    def teardown_method(self):
        self.client.close()

    def test_initialization(self):
        assert self.client.dataset == "test-dataset"
        assert self.client.region == "Île-de-France"
        assert self.client.rows_limit == 10

    @patch.object(ODREClient, "get")
    def test_fetch_consumption(self, mock_get, sample_api_response):
        mock_get.return_value = sample_api_response

        result = self.client.fetch_consumption(limit=2)
        assert result["total_count"] == 2
        assert len(result["results"]) == 2

        mock_get.assert_called_once_with(
            "catalog/datasets/test-dataset/records",
            params={
                "where": 'region="Île-de-France"',
                "limit": 2,
                "offset": 0,
                "order_by": "date_heure DESC",
            },
        )

    @patch.object(ODREClient, "get")
    def test_fetch_consumption_default_limit(self, mock_get, sample_api_response):
        mock_get.return_value = sample_api_response
        self.client.fetch_consumption()

        call_params = mock_get.call_args[1]["params"]
        assert call_params["limit"] == 10  # rows_limit par défaut

    @patch.object(ODREClient, "get")
    def test_fetch_all_consumption_pagination(self, mock_get, sample_api_response):
        # Premier appel retourne 2 résultats, deuxième retourne vide
        empty_response = {"total_count": 2, "results": []}
        mock_get.side_effect = [sample_api_response, empty_response]

        records = self.client.fetch_all_consumption(max_records=100)
        assert len(records) == 2
        assert records[0]["region"] == "Île-de-France"

    @patch.object(ODREClient, "get")
    def test_fetch_all_consumption_respects_max(self, mock_get, sample_api_response):
        mock_get.return_value = sample_api_response

        records = self.client.fetch_all_consumption(max_records=1)
        call_params = mock_get.call_args[1]["params"]
        assert call_params["limit"] == 1

    @patch.object(ODREClient, "get")
    def test_get_dataset_info(self, mock_get, sample_dataset_info):
        mock_get.return_value = sample_dataset_info

        result = self.client.get_dataset_info()
        assert result["dataset"]["dataset_id"] == "consommation-quotidienne-brute-regionale"

    @patch.object(ODREClient, "get")
    def test_fetch_consumption_error(self, mock_get):
        mock_get.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            self.client.fetch_consumption()
