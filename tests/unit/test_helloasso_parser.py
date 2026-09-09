"""
Unit tests for HelloAssoParser.

Run with:
    pytest test_helloasso_parser.py -v
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.parser import HelloAssoParser


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
# HelloAssoParser.parse_email
# ---------------------------------------------------------------------------

class TestHelloAssoParserParseEmail:

    @patch("core.parser.requests.post")
    @patch("builtins.open")
    def test_parse_email_success(self, mock_open, mock_post):
        """Test successful parsing of email content with boolean conversion."""
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "System prompt for parsing email"
        )

        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "adhesions": [
                                {
                                    "first_name": "Jean",
                                    "last_name": "Dupont",
                                    "has_plot": "true",
                                    "amount": 15
                                },
                                {
                                    "first_name": "Marie",
                                    "last_name": "Curie",
                                    "has_plot": False,
                                    "amount": 10
                                }
                            ]
                        })
                    }
                }
            ]
        }
        mock_post.return_value = make_response(status_code=200, json_data=mock_llm_response)

        result = HelloAssoParser.parse_email("Contenu email test", api_key="fake-api-key")

        # Verify that "true" string was converted to boolean True
        assert len(result) == 2
        assert result[0]["first_name"] == "Jean"
        assert result[0]["has_plot"] is True
        assert result[1]["first_name"] == "Marie"
        assert result[1]["has_plot"] is False

        # Verify API request structure
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer fake-api-key"
        assert kwargs["json"]["model"] == "deepseek/deepseek-v4-flash-0731"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}

    @patch("core.parser.requests.post")
    @patch("builtins.open")
    def test_parse_email_empty_adhesions(self, mock_open, mock_post):
        """Test handling when no adhesions are returned."""
        mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"adhesions": []})
                    }
                }
            ]
        }
        mock_post.return_value = make_response(status_code=200, json_data=mock_llm_response)

        result = HelloAssoParser.parse_email("Aucune adhésion", api_key="fake-api-key")

        assert result == []

    @patch("core.parser.requests.post")
    @patch("builtins.open")
    def test_parse_email_http_error(self, mock_open, mock_post):
        """Test HTTP error handling."""
        mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"
        mock_post.return_value = make_response(status_code=500, text="Internal Error")

        with pytest.raises(requests.HTTPError):
            HelloAssoParser.parse_email("Email content", api_key="fake-api-key")

    @patch("core.parser.requests.post")
    @patch("builtins.open")
    def test_parse_email_invalid_json_response(self, mock_open, mock_post):
        """Test error handling when LLM returns non-JSON string."""
        mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": "Not a valid JSON"
                    }
                }
            ]
        }
        mock_post.return_value = make_response(status_code=200, json_data=mock_llm_response)

        with pytest.raises(json.JSONDecodeError):
            HelloAssoParser.parse_email("Email content", api_key="fake-api-key")
