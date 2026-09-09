"""
Integration tests for HelloAssoParser.

These tests interact directly with the real AI Gateway endpoint.
They require a valid AI_GATEWAY_API_KEY environment variable.

Run with:
    pytest -m integration test_helloasso_parser_integration.py -v
"""

import os

import pytest

from core.parser import HelloAssoParser

# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("AI_GATEWAY_API_KEY"),
        reason="Missing AI_GATEWAY_API_KEY environment variable for integration tests.",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures & Helper
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key():
    return os.environ["AI_GATEWAY_API_KEY"]


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestHelloAssoParserIntegration:

    def test_parse_sample_email_integration(self, api_key):
        """Test parsing realistic text email content against the real API."""
        sample_email = """
        Bonjour,
        Nouvelle adhésion reçue via HelloAsso :
        Nom : Dupont
        Prénom : Jean
        Option Parcelle : Oui
        Montant : 15 €
        """

        result = HelloAssoParser.parse_email(sample_email, api_key)

        assert isinstance(result, list)
        if len(result) > 0:
            first = result[0]
            assert isinstance(first, dict)
            assert "first_name" in first or "prenom" in first or "has_plot" in first

    @pytest.mark.parametrize("file_type, content_sample", [
        ("TXT", "Nom: Martin Prénom: Sophie Parcelle: Non"),
        ("HTML", "<div><p>Nom: Martin</p><p>Prénom: Sophie</p><p>Parcelle: Non</p></div>"),
        ("JSON", '{"nom": "Martin", "prenom": "Sophie", "parcelle": false}')
    ])
    def test_parse_formats_robustness(self, api_key, file_type, content_sample):
        """Ensure parser accepts various input text formats without crashing."""
        result = HelloAssoParser.parse_email(content_sample, api_key)
        assert isinstance(result, list)
