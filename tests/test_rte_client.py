"""
Tests unitaires pour RTEClient (OAuth2).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.rte_client import RTEClient


class TestRTEClient:
    """Tests pour la classe RTEClient."""

    def setup_method(self):
        self.client = RTEClient(oauth_token="dGVzdDpzZWNyZXQ=")  # "test:secret" en base64

    def teardown_method(self):
        self.client.close()

    # ── Initialisation ───────────────────────────────────────

    def test_init_with_explicit_token(self):
        assert self.client.oauth_token == "dGVzdDpzZWNyZXQ="
        assert self.client._access_token is None
        assert self.client._token_expiry is None

    def test_init_reads_env_when_no_token(self, monkeypatch):
        monkeypatch.setenv("RTE_API_KEY", "env_token_value")
        client = RTEClient()
        assert client.oauth_token == "env_token_value"
        client.close()

    def test_no_token_returns_empty_list(self, monkeypatch):
        monkeypatch.delenv("RTE_API_KEY", raising=False)
        client = RTEClient(oauth_token="")
        result = client.fetch_actual_generation()
        assert result == []
        client.close()

    # ── Gestion du token OAuth2 ──────────────────────────────

    def _mock_token_response(self, access_token="tok123", expires_in=3600):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": access_token, "expires_in": expires_in}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    @patch("src.ingestion.rte_client.requests.post")
    def test_get_access_token_fetches_and_caches(self, mock_post):
        mock_post.return_value = self._mock_token_response("tok_abc")

        token1 = self.client._get_access_token()
        token2 = self.client._get_access_token()

        assert token1 == "tok_abc"
        assert token2 == "tok_abc"
        mock_post.assert_called_once()  # second call uses cached token

    @patch("src.ingestion.rte_client.requests.post")
    def test_get_access_token_refreshes_when_expired(self, mock_post):
        mock_post.return_value = self._mock_token_response("tok_new")

        self.client._access_token = "tok_old"
        self.client._token_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)

        token = self.client._get_access_token()

        assert token == "tok_new"
        mock_post.assert_called_once()

    @patch("src.ingestion.rte_client.requests.post")
    def test_get_access_token_uses_bearer_header(self, mock_post):
        mock_post.return_value = self._mock_token_response()

        self.client._get_access_token()

        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Basic dGVzdDpzZWNyZXQ="

    # ── fetch_actual_generation ───────────────────────────────

    def _mock_generation_response(self, n_filieres=3):
        records = [{"production_type": f"type_{i}", "values": []} for i in range(n_filieres)]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"actual_generations_per_production_type": records}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    @patch("src.ingestion.rte_client.requests.post")
    def test_fetch_actual_generation_returns_records(self, mock_post):
        mock_post.return_value = self._mock_token_response()
        mock_get = MagicMock(return_value=self._mock_generation_response(5))
        self.client.session.get = mock_get

        result = self.client.fetch_actual_generation(
            start_date="2026-05-01T00:00:00+02:00",
            end_date="2026-05-02T00:00:00+02:00",
        )

        assert len(result) == 5
        assert result[0]["production_type"] == "type_0"

    @patch("src.ingestion.rte_client.requests.post")
    def test_fetch_actual_generation_passes_dates_to_api(self, mock_post):
        mock_post.return_value = self._mock_token_response()
        self.client.session.get = MagicMock(return_value=self._mock_generation_response())

        self.client.fetch_actual_generation(
            start_date="2026-05-01T00:00:00+02:00",
            end_date="2026-05-02T00:00:00+02:00",
        )

        _, kwargs = self.client.session.get.call_args
        assert kwargs["params"]["start_date"] == "2026-05-01T00:00:00+02:00"
        assert kwargs["params"]["end_date"] == "2026-05-02T00:00:00+02:00"

    @patch("src.ingestion.rte_client.requests.post")
    def test_fetch_actual_generation_default_dates_are_yesterday(self, mock_post):
        """Sans dates explicites, la requête couvre la journée complète d'hier."""
        mock_post.return_value = self._mock_token_response()
        self.client.session.get = MagicMock(return_value=self._mock_generation_response())

        self.client.fetch_actual_generation()

        _, kwargs = self.client.session.get.call_args
        start = kwargs["params"]["start_date"]
        end = kwargs["params"]["end_date"]
        # Les deux dates doivent être à minuit (T00:00:00) et séparées de 24h
        assert "T00:00:00" in start
        assert "T00:00:00" in end
        assert start < end

    @patch("src.ingestion.rte_client.requests.post")
    def test_fetch_actual_generation_propagates_http_error(self, mock_post):
        mock_post.return_value = self._mock_token_response()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 400")
        self.client.session.get = MagicMock(return_value=mock_resp)

        with pytest.raises(Exception, match="HTTP 400"):
            self.client.fetch_actual_generation()

    # ── Context manager ──────────────────────────────────────

    def test_context_manager_closes_session(self):
        with RTEClient(oauth_token="tok") as client:
            assert client.session is not None
        # session.close() ne lève pas d'exception — on vérifie que __exit__ passe
