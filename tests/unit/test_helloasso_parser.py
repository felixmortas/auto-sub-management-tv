"""
Unit tests for HelloAssoParser.

HelloAssoParser now delegates all LLM interaction to an injected LLMClient,
so these tests mock `llm_client.call()` directly instead of the HTTP layer.

Run with:
    pytest test_helloasso_parser.py -v
"""

from unittest.mock import MagicMock

import pytest

from core.parser import HelloAssoParser
from services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLMClient whose call() return value is set per test."""
    return MagicMock(spec=LLMClient)


# ---------------------------------------------------------------------------
# HelloAssoParser.parse_email
# ---------------------------------------------------------------------------


class TestHelloAssoParserParseEmail:

    def test_parse_email_converts_string_boolean_has_plot(self, mock_llm_client):
        """A 'true'/'false' string for has_plot should be converted to a Python bool."""
        mock_llm_client.call.return_value = {
            "adhesions": [
                {"first_name": "Jean", "last_name": "Dupont", "has_plot": "true", "amount": 15},
                {"first_name": "Marie", "last_name": "Curie", "has_plot": False, "amount": 10},
            ]
        }

        result = HelloAssoParser.parse_email("Contenu email test", mock_llm_client)

        assert len(result) == 2
        assert result[0]["first_name"] == "Jean"
        assert result[0]["has_plot"] is True
        assert result[1]["first_name"] == "Marie"
        assert result[1]["has_plot"] is False

    def test_parse_email_empty_adhesions(self, mock_llm_client):
        """An explicit empty adhesions list should result in an empty list, without error."""
        mock_llm_client.call.return_value = {"adhesions": []}

        result = HelloAssoParser.parse_email("Aucune adhésion", mock_llm_client)

        assert result == []

    def test_parse_email_missing_adhesions_key_defaults_to_empty_list(self, mock_llm_client):
        """A response with no 'adhesions' key at all should not raise, and default to []."""
        mock_llm_client.call.return_value = {}

        result = HelloAssoParser.parse_email("Contenu inattendu", mock_llm_client)

        assert result == []

    def test_parse_email_calls_llm_client_with_expected_arguments(self, mock_llm_client):
        """parse_email should delegate to llm_client.call with the right prompt file,
        run name, and the raw email content in the user message."""
        mock_llm_client.call.return_value = {"adhesions": []}

        HelloAssoParser.parse_email("Some raw email body", mock_llm_client)

        mock_llm_client.call.assert_called_once()
        _, kwargs = mock_llm_client.call.call_args
        assert kwargs["system_prompt_filename"] == "email_parser.md"
        assert kwargs["run_name"] == "parse_email"
        assert "Some raw email body" in kwargs["user_message"]

    def test_parse_email_propagates_llm_client_errors(self, mock_llm_client):
        """Any exception raised by the underlying LLM client should propagate unchanged."""
        mock_llm_client.call.side_effect = RuntimeError("LLM gateway unavailable")

        with pytest.raises(RuntimeError):
            HelloAssoParser.parse_email("Email content", mock_llm_client)
