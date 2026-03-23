"""
Client spécialisé pour l'API ODRE (Open Data Réseaux Énergies).
Récupère les données de consommation énergétique régionale.
"""
from typing import Any, Optional

from src.ingestion.api_client import APIClient
from config.settings import (
    ODRE_BASE_URL,
    ODRE_DATASET,
    ODRE_REGION,
    ODRE_ROWS_LIMIT,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


class ODREClient(APIClient):
    """Client pour l'API ODRE - consommation énergétique Île-de-France."""

    def __init__(
        self,
        dataset: str = ODRE_DATASET,
        region: str = ODRE_REGION,
        rows_limit: int = ODRE_ROWS_LIMIT,
    ):
        super().__init__(
            base_url=ODRE_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
        )
        self.dataset = dataset
        self.region = region
        self.rows_limit = rows_limit

    def fetch_consumption(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "date_heure DESC",
    ) -> dict[str, Any]:
        """
        Récupère les données de consommation énergétique.

        Args:
            limit: Nombre de lignes à récupérer.
            offset: Décalage pour la pagination.
            order_by: Tri des résultats.

        Returns:
            Données JSON de l'API.
        """
        endpoint = f"catalog/datasets/{self.dataset}/records"
        params = {
            "where": f'region="{self.region}"',
            "limit": limit or self.rows_limit,
            "offset": offset,
            "order_by": order_by,
        }

        try:
            data = self.get(endpoint, params=params)
            total = data.get("total_count", 0)
            records = data.get("results", [])
            self.logger.info(
                "Récupéré %d enregistrements sur %d total", len(records), total
            )
            return data
        except Exception as e:
            self.logger.error("Échec de récupération des données ODRE: %s", e)
            raise

    def fetch_all_consumption(self, max_records: int = 1000) -> list[dict]:
        """
        Récupère toutes les données avec pagination automatique.

        Args:
            max_records: Nombre maximum d'enregistrements à récupérer.

        Returns:
            Liste de tous les enregistrements.
        """
        all_records = []
        offset = 0

        while offset < max_records:
            batch_size = min(self.rows_limit, max_records - offset)
            data = self.fetch_consumption(limit=batch_size, offset=offset)
            records = data.get("results", [])

            if not records:
                break

            all_records.extend(records)
            offset += len(records)
            self.logger.info("Progression: %d/%d enregistrements", len(all_records), max_records)

        self.logger.info("Total récupéré: %d enregistrements", len(all_records))
        return all_records

    def get_dataset_info(self) -> dict[str, Any]:
        """Récupère les métadonnées du dataset."""
        endpoint = f"catalog/datasets/{self.dataset}"
        try:
            return self.get(endpoint)
        except Exception as e:
            self.logger.error("Échec de récupération des métadonnées: %s", e)
            raise
