"""
Classe de scraping web générique avec BeautifulSoup.
Récupère des données complémentaires sur la consommation énergétique.
"""
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.utils.logger import get_logger
from config.settings import REQUEST_TIMEOUT, MAX_RETRIES


class WebScraper:
    """Scraper web générique avec gestion des erreurs."""

    def __init__(
        self,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (compatible; DataPipeline/1.0; "
                "+https://github.com/projet-data)"
            )
        })
        self.logger = get_logger(self.__class__.__name__)

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Télécharge et parse une page HTML.

        Args:
            url: URL de la page à scraper.

        Returns:
            Objet BeautifulSoup ou None en cas d'échec.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(
                    "Scraping %s (tentative %d/%d)", url, attempt, self.max_retries
                )
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return BeautifulSoup(response.text, "lxml")

            except requests.exceptions.RequestException as e:
                self.logger.warning("Erreur scraping tentative %d: %s", attempt, e)
                if attempt == self.max_retries:
                    self.logger.error("Échec après %d tentatives pour %s", self.max_retries, url)
                    raise

        return None

    def extract_tables(self, soup: BeautifulSoup) -> list[list[list[str]]]:
        """
        Extrait toutes les tables HTML d'une page.

        Args:
            soup: Objet BeautifulSoup parsé.

        Returns:
            Liste de tables, chaque table étant une liste de lignes.
        """
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for row in table.find_all("tr"):
                cells = [
                    cell.get_text(strip=True)
                    for cell in row.find_all(["th", "td"])
                ]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    def extract_links(
        self, soup: BeautifulSoup, pattern: Optional[str] = None
    ) -> list[dict[str, str]]:
        """
        Extrait les liens d'une page, optionnellement filtrés par pattern.

        Args:
            soup: Objet BeautifulSoup parsé.
            pattern: Filtre optionnel sur le href.

        Returns:
            Liste de dicts avec 'text' et 'href'.
        """
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if pattern is None or pattern in href:
                links.append({
                    "text": a_tag.get_text(strip=True),
                    "href": href,
                })
        return links

    def close(self):
        """Ferme la session HTTP."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
