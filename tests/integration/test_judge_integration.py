"""
Integration tests for Judge.

These tests interact directly with the real AI Gateway endpoint.
They require a valid AI_GATEWAY_API_KEY environment variable.

Run with:
    pytest -m integration test_judge_integration.py -v
"""

import os

import pytest

from core.judge import Judge

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
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key():
    return os.environ["AI_GATEWAY_API_KEY"]


@pytest.fixture(scope="module")
def sample_members():
    return ["Jean Dupont", "Marie Curie", "Albert Einstein", "Isaac Newton", "Arturo Araùgo"]


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestJudgeIntegration:

    def test_check_names_positive_similarity(self, api_key, sample_members):
        """Test real LLM matching for a name with spelling/accent variations."""
        result = Judge.check_names("Arturo Araujo", sample_members, api_key)

        assert isinstance(result, dict)
        assert "similarity_found" in result
        assert result["similarity_found"] is True

    def test_check_names_negative_similarity(self, api_key, sample_members):
        """Test real LLM matching for a name not in the list."""
        result = Judge.check_names("Charles Darwin", sample_members, api_key)

        assert isinstance(result, dict)
        assert "similarity_found" in result
        assert result["similarity_found"] is False
