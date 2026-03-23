"""
Tests unitaires pour APIClient.
"""
import pytest
import requests
from unittest.mock import patch, MagicMock

from src.ingestion.api_client import APIClient


class TestAPIClient:
    """Tests pour la classe APIClient."""

    def setup_method(self):
        self.client = APIClient(
            base_url="https://api.example.com",
            timeout=5,
            max_retries=2,
            retry_delay=0,  # Pas d'attente dans les tests
        )

    def teardown_method(self):
        self.client.close()

    def test_build_url(self):
        assert self.client._build_url("/endpoint") == "https://api.example.com/endpoint"
        assert self.client._build_url("endpoint") == "https://api.example.com/endpoint"

    def test_build_url_strips_trailing_slash(self):
        client = APIClient(base_url="https://api.example.com/")
        assert client._build_url("test") == "https://api.example.com/test"
        client.close()

    @patch("src.ingestion.api_client.requests.Session.get")
    def test_get_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.client.get("/test")
        assert result == {"data": "test"}
        mock_get.assert_called_once()

    @patch("src.ingestion.api_client.requests.Session.get")
    def test_get_with_params(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.client.get("/test", params={"key": "value"})
        mock_get.assert_called_once_with(
            "https://api.example.com/test",
            params={"key": "value"},
            timeout=5,
        )

    @patch("src.ingestion.api_client.requests.Session.get")
    def test_get_retry_on_connection_error(self, mock_get):
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
        ]

        with pytest.raises(requests.exceptions.ConnectionError):
            self.client.get("/test")

        assert mock_get.call_count == 2

    @patch("src.ingestion.api_client.requests.Session.get")
    def test_get_retry_on_timeout(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "ok"}
        mock_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            mock_response,
        ]

        result = self.client.get("/test")
        assert result == {"data": "ok"}
        assert mock_get.call_count == 2

    @patch("src.ingestion.api_client.requests.Session.get")
    def test_get_no_retry_on_client_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found", response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            self.client.get("/test")

        assert mock_get.call_count == 1

    def test_context_manager(self):
        with APIClient(base_url="https://api.example.com") as client:
            assert client.base_url == "https://api.example.com"
