"""
Integration tests for JevClient.

These tests interact directly with the real AI Gateway "evaluate" endpoint
and check the low-level HTTP/JSON/tracing plumbing for the Jev evaluation
model (typesafe-ai/jev), independently of any business logic living in
Judge or HelloAssoParser.

Requires the following environment variables:
    AI_GATEWAY_API_KEY  - Bearer token for the AI Gateway.

Run with:
    pytest -m integration test_jev_client_integration.py -v
"""

import os

import pytest
import requests

from services.jev_client import JevChoiceResult, JevClient

# ---------------------------------------------------------------------------
# Skip condition
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("AI_GATEWAY_API_KEY"),
        reason="Missing AI_GATEWAY_API_KEY environment variables for integration tests.",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jev_client(tracer):
    """Build a real JevClient pointed at the actual AI Gateway."""
    return JevClient(
        model="typesafe-ai/jev",
        url="https://ai-gateway.vercel.sh/v1/evaluate",
        api_key=os.environ["AI_GATEWAY_API_KEY"],
        tracer=tracer,
    )


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestJevClientIntegration:

    def test_ask_boolean_returns_probability_for_names_similarity_prompt(self, jev_client):
        """A real 'boolean' question should return a float probability in [0, 1]."""
        probability = jev_client.ask_boolean(
            system_prompt_filename="names_similarity_judge_noul.md",
            state={
                "full_name": "Jean Dupont",
                "candidate_names": ["Jean Dupont"],
            },
            run_name="integration_jev_boolean",
        )

        assert isinstance(probability, float)
        assert 0.0 <= probability <= 1.0

    def test_ask_choice_returns_resolved_choice_result(self, jev_client):
        """A real 'choice' question should resolve back to an original candidate
        name (not the internal 'member_x' key) and expose consistent metadata.
        """
        members_names = ["Jean Dupont", "Jeanne Dupond", "Paul Martin"]

        result = jev_client.ask_choice(
            system_prompt_filename="names_similarity_judge_choice.md",
            full_name="Jean Dupont",
            members_names=members_names,
            run_name="integration_jev_choice",
        )

        assert isinstance(result, JevChoiceResult)
        # The resolved choice must be one of the original candidate names,
        # never an internal "member_0"-style key.
        assert result.choice in members_names
        assert not result.choice.startswith("member_")

        # Probabilities should be keyed by original candidate names too.
        assert set(result.probabilities.keys()).issubset(set(members_names))
        for probability in result.probabilities.values():
            assert 0.0 <= probability <= 1.0

        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.raw_answer, dict)

    def test_call_raises_on_invalid_api_key(self, tracer):
        """An invalid API key should surface as an HTTP error from the gateway."""
        client = JevClient(
            model="typesafe-ai/jev",
            url="https://ai-gateway.vercel.sh/v1/evaluate",
            api_key="invalid-key",
            tracer=tracer,
        )

        with pytest.raises(requests.HTTPError):
            client.ask_boolean(
                system_prompt_filename="names_similarity_judge_noul.md",
                state={"full_name": "Jean Dupont", "candidate_names": ["Jean Dupont"]},
                run_name="integration_jev_invalid_key",
            )
