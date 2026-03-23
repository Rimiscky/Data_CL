"""
Tests unitaires pour WebScraper.
"""
import pytest
import requests
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

from src.ingestion.scraper import WebScraper


class TestWebScraper:
    """Tests pour la classe WebScraper."""

    def setup_method(self):
        self.scraper = WebScraper(timeout=5, max_retries=2)

    def teardown_method(self):
        self.scraper.close()

    @patch("src.ingestion.scraper.requests.Session.get")
    def test_fetch_page_success(self, mock_get, sample_html):
        mock_response = MagicMock()
        mock_response.text = sample_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        soup = self.scraper.fetch_page("https://example.com")
        assert soup is not None
        assert isinstance(soup, BeautifulSoup)
        assert soup.find("h1").text == "Données éCO2mix"

    @patch("src.ingestion.scraper.requests.Session.get")
    def test_fetch_page_retry_then_success(self, mock_get, sample_html):
        mock_response = MagicMock()
        mock_response.text = sample_html
        mock_response.raise_for_status.return_value = None

        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Failed"),
            mock_response,
        ]

        soup = self.scraper.fetch_page("https://example.com")
        assert soup is not None
        assert mock_get.call_count == 2

    @patch("src.ingestion.scraper.requests.Session.get")
    def test_fetch_page_all_retries_fail(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Failed")

        with pytest.raises(requests.exceptions.ConnectionError):
            self.scraper.fetch_page("https://example.com")

        assert mock_get.call_count == 2

    def test_extract_tables(self, sample_html):
        soup = BeautifulSoup(sample_html, "lxml")
        tables = self.scraper.extract_tables(soup)

        assert len(tables) == 1
        assert tables[0][0] == ["Région", "Consommation (MW)"]
        assert tables[0][1] == ["Île-de-France", "15200"]
        assert tables[0][2] == ["Auvergne-Rhône-Alpes", "8900"]

    def test_extract_links_all(self, sample_html):
        soup = BeautifulSoup(sample_html, "lxml")
        links = self.scraper.extract_links(soup)

        assert len(links) == 2
        assert links[0]["href"] == "https://example.com/download/data.csv"

    def test_extract_links_with_pattern(self, sample_html):
        soup = BeautifulSoup(sample_html, "lxml")
        links = self.scraper.extract_links(soup, pattern="download")

        assert len(links) == 1
        assert "download" in links[0]["href"]

    def test_context_manager(self):
        with WebScraper() as scraper:
            assert scraper.session is not None
