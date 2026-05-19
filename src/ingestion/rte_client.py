"""
Client pour l'API RTE OAuth2 (digital.iservices.rte-france.com).
Récupère les données de génération réelle par filière (nucléaire, éolien, solaire, etc.).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

from src.utils.logger import get_logger
from config.settings import REQUEST_TIMEOUT

RTE_TOKEN_URL = "https://digital.iservices.rte-france.com/token/oauth/"
RTE_API_BASE = "https://digital.iservices.rte-france.com/open_api/actual_generation/v1"
PARIS_TZ = ZoneInfo("Europe/Paris")


class RTEClient:
    """Client OAuth2 pour l'API RTE — génération réelle par filière."""

    def __init__(self, oauth_token: str = ""):
        self.oauth_token = oauth_token or os.getenv("RTE_API_KEY", "")
        self.logger = get_logger(self.__class__.__name__)
        self.session = requests.Session()
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _get_access_token(self) -> str:
        """Obtient un access token OAuth2 via client credentials."""
        if self._access_token and self._token_expiry and datetime.now(timezone.utc) < self._token_expiry:
            return self._access_token

        self.logger.info("Obtention du token OAuth2 RTE...")
        response = requests.post(
            RTE_TOKEN_URL,
            headers={
                "Authorization": f"Basic {self.oauth_token}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        self.logger.info("Token OAuth2 obtenu (expire dans %ds)", expires_in)
        return self._access_token

    def fetch_actual_generation(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Récupère la génération réelle par filière.

        Args:
            start_date: Date début ISO8601 (ex: 2026-05-01T00:00:00+02:00)
            end_date: Date fin ISO8601

        Returns:
            Liste des enregistrements de génération.
        """
        if not self.oauth_token:
            self.logger.warning("RTE_API_KEY non configuré, ingestion RTE ignorée")
            return []

        def _fmt(dt: datetime) -> str:
            s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
            return s[:-2] + ":" + s[-2:]

        if end_date is None:
            end_date = _fmt(datetime.now(PARIS_TZ))
        if start_date is None:
            start_date = _fmt(datetime.now(PARIS_TZ) - timedelta(days=1))

        try:
            token = self._get_access_token()
            response = self.session.get(
                f"{RTE_API_BASE}/actual_generations_per_production_type",
                headers={"Authorization": f"Bearer {token}"},
                params={"start_date": start_date, "end_date": end_date},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            records = data.get("actual_generations_per_production_type", [])
            self.logger.info("Récupéré %d filières de génération RTE", len(records))
            return records
        except Exception as e:
            self.logger.error("Échec récupération génération RTE: %s", e)
            raise

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
