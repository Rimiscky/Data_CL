"""
Classe de base réutilisable pour les appels API REST.
Gère les retries, timeouts et la sérialisation des réponses.
"""
import time
from typing import Any, Optional

import requests

from src.utils.logger import get_logger


class APIClient:
    """Client HTTP générique avec gestion des erreurs et retries."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.logger = get_logger(self.__class__.__name__)

    def _build_url(self, endpoint: str) -> str:
        """Construit l'URL complète à partir d'un endpoint."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get(
        self, endpoint: str, params: Optional[dict] = None
    ) -> dict[str, Any]:
        """
        Effectue une requête GET avec retry automatique.

        Args:
            endpoint: Le chemin de l'API.
            params: Paramètres de la requête.

        Returns:
            La réponse JSON parsée.

        Raises:
            requests.exceptions.RequestException: Si toutes les tentatives échouent.
        """
        url = self._build_url(endpoint)
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(
                    "GET %s (tentative %d/%d)", url, attempt, self.max_retries
                )
                response = self.session.get(
                    url, params=params, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                self.logger.warning("Erreur HTTP %s: %s", response.status_code, e)
                last_exception = e
                if response.status_code < 500:
                    raise

            except requests.exceptions.ConnectionError as e:
                self.logger.warning("Erreur de connexion: %s", e)
                last_exception = e

            except requests.exceptions.Timeout as e:
                self.logger.warning("Timeout: %s", e)
                last_exception = e

            if attempt < self.max_retries:
                wait = self.retry_delay * attempt
                self.logger.info("Attente de %ds avant retry...", wait)
                time.sleep(wait)

        raise last_exception

    def close(self):
        """Ferme la session HTTP."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
