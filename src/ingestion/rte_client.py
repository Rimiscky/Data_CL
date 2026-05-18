"""
Client spécialisé pour l'API RTE (Réseau de Transport d'Électricité).
Récupère les données de génération d'électricité en temps réel et historiques.
"""
from typing import Any, Optional

from src.ingestion.api_client import APIClient
from config.settings import (
    RTE_API_BASE_URL,
    RTE_API_KEY,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
)


class RTEClient(APIClient):
    """Client pour l'API RTE - génération d'électricité nationale."""

    def __init__(
        self,
        api_key: str = RTE_API_KEY,
    ):
        super().__init__(
            base_url=RTE_API_BASE_URL,
            timeout=REQUEST_TIMEOUT,
            max_retries=MAX_RETRIES,
            retry_delay=RETRY_DELAY,
        )
        self.api_key = api_key
        if self.api_key:
            # guard : permet d'instancier le client sans clé en dev/test sans lever d'erreur
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def fetch_generation_mix(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = "date DESC",
    ) -> dict[str, Any]:
        """
        Récupère les données de mix de génération d'électricité.

        Args:
            limit: Nombre de lignes à récupérer.
            offset: Décalage pour la pagination.
            order_by: Tri des résultats.

        Returns:
            Données JSON de l'API.
        """
        endpoint = "catalog/datasets/generation-par-filiere/records"
        params = {
            "limit": limit or 100,
            "offset": offset,
            "order_by": order_by,
        }

        try:
            data = self.get(endpoint, params=params)
            total = data.get("total_count", 0)
            records = data.get("results", [])
            self.logger.info(
                "Récupéré %d enregistrements génération sur %d total", len(records), total
            )
            return data
        except Exception as e:
            self.logger.error("Échec de récupération des données RTE: %s", e)
            raise

    def fetch_all_generation(self, max_records: int = 1000) -> list[dict]:
        """
        Récupère toutes les données de génération avec pagination automatique.

        Args:
            max_records: Nombre maximum d'enregistrements à récupérer.

        Returns:
            Liste de tous les enregistrements.
        """
        all_records = []
        offset = 0
        batch_size = 100  # taille de page max documentée par l'API RTE

        while offset < max_records:
            current_limit = min(batch_size, max_records - offset)  # dernière page peut être plus petite
            data = self.fetch_generation_mix(limit=current_limit, offset=offset)
            records = data.get("results", [])

            if not records:
                break

            all_records.extend(records)
            offset += len(records)  # avance du nombre réel retourné, pas du current_limit
            self.logger.info(
                "Progression: %d/%d enregistrements génération",
                len(all_records),
                max_records,
            )

        self.logger.info("Total récupéré: %d enregistrements génération", len(all_records))
        return all_records

    def get_dataset_info(self) -> dict[str, Any]:
        """Récupère les métadonnées du dataset de génération."""
        endpoint = "catalog/datasets/generation-par-filiere"
        try:
            return self.get(endpoint)
        except Exception as e:
            self.logger.error("Échec de récupération des métadonnées RTE: %s", e)
            raise
