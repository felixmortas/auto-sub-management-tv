"""
Unit tests for Judge.

Judge now delegates all LLM interaction to an injected LLMClient, so these
tests mock `llm_client.call()` directly instead of the HTTP layer.

Run with:
    pytest test_judge.py -v
"""

from unittest.mock import MagicMock

import pytest

from core.judge import Judge
from services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLMClient whose call() return value is set per test."""
    return MagicMock(spec=LLMClient)


# ---------------------------------------------------------------------------
# Judge.check_names
# ---------------------------------------------------------------------------


class TestJudgeCheckNames:

    def test_check_names_converts_string_boolean_to_bool(self, mock_llm_client):
        """A 'true' string returned by the LLM should be converted to Python True."""
        mock_llm_client.call.return_value = {
            "similarity_found": "true",
            "matched_name": "Arturo Araùgo",
            "confidence": 0.95,
            "reasoning": "Variante accentuée et coquille mineure",
        }

        members = ["Jean Dupont", "Arturo Araùgo"]
        result = Judge.check_names("Arturo Araujo", members, mock_llm_client)

        assert result["similarity_found"] is True
        assert result["matched_name"] == "Arturo Araùgo"
        assert result["confidence"] == 0.95

    def test_check_names_leaves_native_boolean_untouched(self, mock_llm_client):
        """A native Python bool returned by the LLM should pass through unchanged."""
        mock_llm_client.call.return_value = {
            "similarity_found": False,
            "matched_name": None,
            "confidence": 0.0,
            "reasoning": "Aucune correspondance dans la liste",
        }

        result = Judge.check_names("Charles Darwin", ["Jean Dupont"], mock_llm_client)

        assert result["similarity_found"] is False
        assert result["matched_name"] is None

    def test_check_names_calls_llm_client_with_expected_arguments(self, mock_llm_client):
        """check_names should delegate to llm_client.call with the right prompt file,
        run name, and a user message containing both the candidate and member names."""
        mock_llm_client.call.return_value = {"similarity_found": False}

        Judge.check_names("Charles Darwin", ["Jean Dupont", "Marie Curie"], mock_llm_client)

        mock_llm_client.call.assert_called_once()
        _, kwargs = mock_llm_client.call.call_args
        assert kwargs["system_prompt_filename"] == "names_similarity_judge.md"
        assert kwargs["run_name"] == "check_names"
        assert "Charles Darwin" in kwargs["user_message"]
        assert "Jean Dupont" in kwargs["user_message"]
        assert "Marie Curie" in kwargs["user_message"]

    def test_check_names_propagates_llm_client_errors(self, mock_llm_client):
        """Any exception raised by the underlying LLM client should propagate unchanged."""
        mock_llm_client.call.side_effect = RuntimeError("LLM gateway unavailable")

        with pytest.raises(RuntimeError):
            Judge.check_names("Charles Darwin", ["Jean Dupont"], mock_llm_client)
