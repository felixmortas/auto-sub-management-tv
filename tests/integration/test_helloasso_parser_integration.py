"""
Integration tests for HelloAssoParser.

These tests build a real LLMClient (talking to the actual AI Gateway) and
inject it into HelloAssoParser, to validate the end-to-end business behavior.

Run with:
    pytest -m integration test_helloasso_parser_integration.py -v
"""

import os

import pytest

from core.parser import HelloAssoParser
from services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("AI_GATEWAY_API_KEY") or not os.environ.get("AI_GATEWAY_URL"),
        reason="Missing AI_GATEWAY_API_KEY/AI_GATEWAY_URL environment variables for integration tests.",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def llm_client(tracer):
    """Build a real LLMClient pointed at the actual AI Gateway."""
    return LLMClient(
        model=os.environ.get("AI_GATEWAY_MODEL", "deepseek/deepseek-v4-flash-0731"),
        url=os.environ["AI_GATEWAY_URL"],
        api_key=os.environ["AI_GATEWAY_API_KEY"],
        tracer=tracer,
    )


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestHelloAssoParserIntegration:

    def test_parse_sample_email_integration(self, llm_client):
        """Parsing a realistic French adhesion email should return a list of adhesion dicts."""
        sample_email = """
        Bonjour,
        Nouvelle adhésion reçue via HelloAsso :
        Nom : Dupont
        Prénom : Jean
        Option Parcelle : Oui
        Montant : 15 €
        """

        result = HelloAssoParser.parse_email(sample_email, llm_client)

        assert isinstance(result, list)
        if len(result) > 0:
            first = result[0]
            assert isinstance(first, dict)
            assert "first_name" in first or "prenom" in first or "has_plot" in first

    @pytest.mark.parametrize(
        "file_type, content_sample",
        [
            ("TXT", "Nom: Martin Prénom: Sophie Parcelle: Non"),
            ("HTML", "<div><p>Nom: Martin</p><p>Prénom: Sophie</p><p>Parcelle: Non</p></div>"),
            ("JSON", '{"nom": "Martin", "prenom": "Sophie", "parcelle": false}'),
        ],
    )
    def test_parse_formats_robustness(self, llm_client, file_type, content_sample):
        """The parser should accept various raw text formats without crashing."""
        result = HelloAssoParser.parse_email(content_sample, llm_client)
        assert isinstance(result, list)
