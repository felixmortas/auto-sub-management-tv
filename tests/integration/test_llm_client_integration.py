"""
Integration tests for LLMClient.

These tests interact directly with the real AI Gateway endpoint and check
the low-level HTTP/JSON/tracing plumbing, independently of any business
logic living in Judge or HelloAssoParser.

Requires the following environment variables:
    AI_GATEWAY_API_KEY  - Bearer token for the AI Gateway.
    AI_GATEWAY_URL      - Chat completions endpoint URL.
    AI_GATEWAY_MODEL    - Optional, defaults to "deepseek/deepseek-v4-flash-0731".

Run with:
    pytest -m integration test_llm_client_integration.py -v
"""

import os

import pytest
import requests

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


class TestLLMClientIntegration:

    def test_call_returns_dict_for_email_parser_prompt(self, llm_client):
        """A real call using the email parser prompt should return a parsed dict."""
        result = llm_client.call(
            system_prompt_filename="email_parser.md",
            user_message="Nom: Dupont Prénom: Jean Parcelle: Oui Montant: 15 €",
            run_name="integration_email_parser",
        )

        assert isinstance(result, dict)
        assert "adhesions" in result

    def test_call_returns_dict_for_names_similarity_prompt(self, llm_client):
        """A real call using the names similarity prompt should return a parsed dict."""
        result = llm_client.call(
            system_prompt_filename="names_similarity_judge.md",
            user_message=(
                "Nom complet à comparer : Jean Dupont\n\n"
                "Noms des membres de l'année précédente :\n['Jean Dupont']"
            ),
            run_name="integration_names_similarity",
        )

        assert isinstance(result, dict)
        assert "similarity_found" in result

    def test_call_raises_on_invalid_api_key(self, tracer):
        """An invalid API key should surface as an HTTP error from the gateway."""
        client = LLMClient(
            model=os.environ.get("AI_GATEWAY_MODEL", "deepseek/deepseek-v4-flash-0731"),
            url=os.environ["AI_GATEWAY_URL"],
            api_key="invalid-key",
            tracer=tracer,
        )

        with pytest.raises(requests.HTTPError):
            client.call(
                system_prompt_filename="email_parser.md",
                user_message="Nom: Dupont Prénom: Jean",
                run_name="integration_invalid_key",
            )
