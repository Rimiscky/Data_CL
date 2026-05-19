"""
Fixtures partagées pour les tests.
"""
import sys
from pathlib import Path

import pytest

# Ajouter la racine du projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def sample_api_response():
    """Réponse simulée de l'API ODRE."""
    return {
        "total_count": 2,
        "results": [
            {
                "date_heure": "2024-01-15T12:00:00+00:00",
                "code_insee_region": "11",
                "region": "Île-de-France",
                "consommation_brute_electricite_rte": 15200,
                "consommation_brute_gaz_totale": 8500,
            },
            {
                "date_heure": "2024-01-15T11:00:00+00:00",
                "code_insee_region": "11",
                "region": "Île-de-France",
                "consommation_brute_electricite_rte": 14800,
                "consommation_brute_gaz_totale": 8300,
            },
        ],
    }


@pytest.fixture
def sample_dataset_info():
    """Métadonnées simulées du dataset ODRE."""
    return {
        "dataset": {
            "dataset_id": "consommation-quotidienne-brute-regionale",
            "metas": {"default": {"title": "Consommation quotidienne brute régionale"}},
        }
    }


@pytest.fixture
def sample_html():
    """Page HTML simulée pour le scraping."""
    return """
    <html>
    <body>
        <h1>Données éCO2mix</h1>
        <table>
            <tr><th>Région</th><th>Consommation (MW)</th></tr>
            <tr><td>Île-de-France</td><td>15200</td></tr>
            <tr><td>Auvergne-Rhône-Alpes</td><td>8900</td></tr>
        </table>
        <a href="https://example.com/download/data.csv">Télécharger CSV</a>
        <a href="https://example.com/page">Autre lien</a>
    </body>
    </html>
    """


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Répertoire temporaire pour les tests de sauvegarde."""
    return tmp_path / "test_data"
