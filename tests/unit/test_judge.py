"""
Unit tests for Judge.

Run with:
    pytest test_judge.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.judge import Judge


# ---------------------------------------------------------------------------
# Helper function
# ---------------------------------------------------------------------------

def make_response(status_code=200, json_data=None, text=""):
    """Build a fake requests.Response-like object."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.text = text
    mock_response.json.return_value = json_data or {}

    def raise_for_status():
        if status_code >= 400:
            raise requests.HTTPError(f"HTTP {status_code}")

    mock_response.raise_for_status.side_effect = raise_for_status
    return mock_response


# ---------------------------------------------------------------------------
# Judge.check_names
# ---------------------------------------------------------------------------

class TestJudgeCheckNames:

    @patch("core.judge.requests.post")
    @patch("builtins.open")
    def test_check_names_similarity_found_string_boolean(self, mock_open, mock_post):
        """Test check_names converts string boolean 'true' to Python True."""
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "System prompt for judging names"
        )

        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "similarity_found": "true",
                            "matched_name": "Arturo Araùgo",
                            "confidence": 0.95,
                            "reasoning": "Variante accentuée et coquille mineure"
                        })
                    }
                }
            ]
        }
        mock_post.return_value = make_response(status_code=200, json_data=mock_llm_response)

        members = ["Jean Dupont", "Arturo Araùgo"]
        result = Judge.check_names("Arturo Araujo", members, api_key="fake-api-key")

        assert result["similarity_found"] is True
        assert result["matched_name"] == "Arturo Araùgo"
        assert result["confidence"] == 0.95

        # Verify payload details
        mock_post.assert_called_once()
        kwargs = mock_post.call_args[1]
        assert kwargs["headers"]["Authorization"] == "Bearer fake-api-key"
        assert "Arturo Araujo" in kwargs["json"]["messages"][1]["content"]

    @patch("core.judge.requests.post")
    @patch("builtins.open")
    def test_check_names_no_similarity(self, mock_open, mock_post):
        """Test check_names when no match is found."""
        mock_open.return_value.__enter__.return_value.read.return_value = "Prompt"
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "similarity_found": False,
                            "matched_name": None,
                            "confidence": 0.0,
                            "reasoning": "Aucune correspondance dans la liste"
                        })
                    }
                }
            ]
        }
        mock_post.return_value = make_response(status_code=200, json_data=mock_llm_response)

        result = Judge.check_names("Charles Darwin", ["Jean Dupont"], api_key="fake-api-key")

        assert result["similarity_found"] is False
        assert result["matched_name"] is None

    @patch("core.judge.requests.post")
    @patch("builtins.open")
    def test_check_names_raises_http_error(self, mock_open, mock_post):
        """Test exception propagation on API error."""
        mock_open.return_value.__enter__.return_value.read.return_value = "Prompt"
        mock_post.return_value = make_response(status_code=401, text="Unauthorized")

        with pytest.raises(requests.HTTPError):
            Judge.check_names("Unknown Name", ["Jean Dupont"], api_key="invalid-key")
