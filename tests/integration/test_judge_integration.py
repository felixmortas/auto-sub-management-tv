"""
Integration tests for Judge.

These tests build a real LLMClient (talking to the actual AI Gateway) and
inject it into Judge, to validate the end-to-end business behavior.

Run with:
    pytest -m integration test_judge_integration.py -v
"""

import os

import pytest

from core.judge import Judge
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


@pytest.fixture
def sample_members():
    """Reference list of member names used as the comparison pool."""
    return ["Jean Dupont", "Marie Curie", "Albert Einstein", "Isaac Newton", "Arturo Araùgo"]


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestJudgeIntegration:

    def test_check_names_positive_similarity(self, llm_client, sample_members):
        """A name that is a spelling/accent variation of a known member should match."""
        result = Judge.check_names("Arturo Araujo", sample_members, llm_client)

        assert isinstance(result, dict)
        assert "similarity_found" in result
        assert result["similarity_found"] is True

    def test_check_names_negative_similarity(self, llm_client, sample_members):
        """A name absent from the member list should not be reported as a match."""
        result = Judge.check_names("Charles Darwin", sample_members, llm_client)

        assert isinstance(result, dict)
        assert "similarity_found" in result
        assert result["similarity_found"] is False
