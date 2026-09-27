"""
Unit tests for JevClient.

Most tests use the shared `tracer` fixture (a real LangSmithTracer, explicitly
disabled - see conftest.py), which exercises the same code path as production
without making network calls. The couple of tests that need to inspect what
JevClient actually writes onto the run object build a local
MagicMock(spec=LangSmithTracer) instead, as recommended by that fixture's
docstring.

Run with:
    pytest test_jev_client.py -v
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.jev_client import JevChoiceResult, JevClient
from services.langsmith_tracer import LangSmithTracer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_http_response(status_code=200, json_data=None, text=""):
    """Build a fake requests.Response-like object.

    `.ok` is set explicitly (mirroring the real `requests.Response.ok`
    property, i.e. status_code < 400): JevClient branches on `response.ok`
    (unlike LLMClient, which just calls `raise_for_status()`
    unconditionally), so a MagicMock's default truthy `.ok` would silently
    skip the error path and mask failures.
    """
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = status_code
    mock_response.ok = status_code < 400
    mock_response.text = text
    mock_response.json.return_value = json_data or {}

    def raise_for_status():
        if status_code >= 400:
            raise requests.HTTPError(f"HTTP {status_code}")

    mock_response.raise_for_status.side_effect = raise_for_status
    return mock_response


def make_answers_payload(answer, question_key="question"):
    """Build a fake Jev API response body.

    `answer` is the raw dict Jev returns for the single question sent in the
    request. The key it's nested under is deliberately configurable (and
    defaults to something other than a "real" semantic name) to exercise the
    fact that JevClient never relies on knowing that key.
    """
    return {"answers": {question_key: answer}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jev_client(tracer):
    """Build a JevClient wired to the shared (disabled) tracer fixture."""
    return JevClient(
        model="typesafe-ai/jev",
        url="https://fake-gateway.test/v1/evaluate",
        api_key="fake-api-key",
        tracer=tracer,
    )


# ---------------------------------------------------------------------------
# JevClient.ask_boolean - happy path
# ---------------------------------------------------------------------------


class TestJevClientAskBooleanSuccess:

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="Is this a match?")
    def test_ask_boolean_returns_probability(self, mock_load_prompt, mock_post, jev_client):
        """ask_boolean() should return the probability of the sole answer, whatever
        key it was nested under in the response."""
        payload = make_answers_payload({"probability": 0.87}, question_key="weird_key")
        mock_post.return_value = make_http_response(json_data=payload)

        result = jev_client.ask_boolean(
            system_prompt_filename="dummy_prompt.md",
            state={"full_name": "Jane Doe", "candidate": "J. Doe"},
        )

        assert result == 0.87

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_ask_boolean_sends_correct_request_payload(self, mock_load_prompt, mock_post, jev_client):
        """The HTTP request should carry the model, the raw state, a single
        'boolean' question with the loaded instructions, and the auth header."""
        payload = make_answers_payload({"probability": 0.5})
        mock_post.return_value = make_http_response(json_data=payload)

        state = {"full_name": "Jane Doe", "candidate": "J. Doe"}
        jev_client.ask_boolean(
            system_prompt_filename="dummy_prompt.md",
            state=state,
            run_name="test_run",
        )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args

        assert kwargs["headers"]["Authorization"] == "Bearer fake-api-key"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert kwargs["json"]["model"] == "typesafe-ai/jev"
        assert kwargs["json"]["state"] == state

        # Exactly one question is sent, under an arbitrary internal key whose
        # name callers never need to know or provide.
        questions = kwargs["json"]["questions"]
        assert len(questions) == 1
        (question,) = questions.values()
        assert question == {"type": "boolean", "instructions": "System instructions"}

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_ask_boolean_uses_default_run_name(self, mock_load_prompt, mock_post, jev_client):
        """When run_name isn't provided, ask_boolean should fall back to its default."""
        payload = make_answers_payload({"probability": 0.5})
        mock_post.return_value = make_http_response(json_data=payload)

        mock_tracer = MagicMock(spec=LangSmithTracer)
        mock_tracer.trace_llm_run.return_value.__enter__.return_value = {}
        jev_client.tracer = mock_tracer

        jev_client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={})

        call_args, _call_kwargs = mock_tracer.trace_llm_run.call_args
        assert call_args[0] == "jev_boolean_call"


# ---------------------------------------------------------------------------
# JevClient.ask_choice - happy path
# ---------------------------------------------------------------------------


class TestJevClientAskChoiceSuccess:

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="Pick the best match")
    def test_ask_choice_sends_stable_member_keys(self, mock_load_prompt, mock_post, jev_client):
        """Candidate names should be sent as 'member_N' criteria, keyed by their
        position, rather than the raw names themselves."""
        payload = make_answers_payload(
            {"choice": "member_1", "probabilities": {"member_0": 0.1, "member_1": 0.9}, "confidence": 0.9}
        )
        mock_post.return_value = make_http_response(json_data=payload)

        jev_client.ask_choice(
            system_prompt_filename="dummy_prompt.md",
            full_name="Jane Doe",
            members_names=["Jane D.", "Jane Doe"],
        )

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["state"] == "Jane Doe"

        (question,) = kwargs["json"]["questions"].values()
        assert question["type"] == "choice"
        assert question["instructions"] == "Pick the best match"
        assert question["criteria"] == {"member_0": "Jane D.", "member_1": "Jane Doe"}

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="Pick the best match")
    def test_ask_choice_resolves_member_keys_back_to_names(self, mock_load_prompt, mock_post, jev_client):
        """The returned JevChoiceResult should expose original candidate names,
        not the internal 'member_N' identifiers used in the request."""
        raw_answer = {
            "choice": "member_1",
            "probabilities": {"member_0": 0.1, "member_1": 0.9},
            "confidence": 0.9,
        }
        payload = make_answers_payload(raw_answer)
        mock_post.return_value = make_http_response(json_data=payload)

        result = jev_client.ask_choice(
            system_prompt_filename="dummy_prompt.md",
            full_name="Jane Doe",
            members_names=["Jane D.", "Jane Doe"],
        )

        assert isinstance(result, JevChoiceResult)
        assert result.choice == "Jane Doe"
        assert result.probabilities == {"Jane D.": 0.1, "Jane Doe": 0.9}
        assert result.confidence == 0.9
        assert result.raw_answer == raw_answer

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="Pick the best match")
    def test_ask_choice_falls_back_to_raw_key_when_unresolvable(self, mock_load_prompt, mock_post, jev_client):
        """An unexpected/unknown key in the answer should be passed through as-is
        instead of crashing the caller."""
        raw_answer = {
            "choice": "some_unexpected_key",
            "probabilities": {"some_unexpected_key": 1.0},
            "confidence": 0.42,
        }
        payload = make_answers_payload(raw_answer)
        mock_post.return_value = make_http_response(json_data=payload)

        result = jev_client.ask_choice(
            system_prompt_filename="dummy_prompt.md",
            full_name="Jane Doe",
            members_names=["Jane D.", "Jane Doe"],
        )

        assert result.choice == "some_unexpected_key"
        assert result.probabilities == {"some_unexpected_key": 1.0}

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="Pick the best match")
    def test_ask_choice_handles_missing_probabilities(self, mock_load_prompt, mock_post, jev_client):
        """A response without a 'probabilities' field should not crash; it should
        resolve to an empty probabilities dict."""
        raw_answer = {"choice": "member_0", "confidence": 0.6}
        payload = make_answers_payload(raw_answer)
        mock_post.return_value = make_http_response(json_data=payload)

        result = jev_client.ask_choice(
            system_prompt_filename="dummy_prompt.md",
            full_name="Jane Doe",
            members_names=["Jane D."],
        )

        assert result.choice == "Jane D."
        assert result.probabilities == {}


# ---------------------------------------------------------------------------
# JevClient - tracing
#
# These tests build a dedicated JevClient with a local MagicMock(spec=LangSmithTracer)
# instead of using the shared `tracer` fixture, specifically to inspect the run
# object that JevClient writes to.
# ---------------------------------------------------------------------------


class TestJevClientTracing:

    def _build_client_with_mock_tracer(self):
        """Build a JevClient plus a mock tracer whose yielded run is a real dict,
        so writes to it (run.update({...})) can be asserted on afterwards."""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        run = MagicMock()
        mock_tracer.trace_llm_run.return_value.__enter__.return_value = run

        client = JevClient(
            model="typesafe-ai/jev",
            url="https://fake-gateway.test/v1/evaluate",
            api_key="fake-api-key",
            tracer=mock_tracer,
        )
        return client, mock_tracer, run

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_call_forwards_provider_and_model_name_as_metadata(self, mock_load_prompt, mock_post):
        """The provider/model split of self.model should be forwarded as tracer
        metadata, same convention as LLMClient."""
        payload = make_answers_payload({"probability": 0.5})
        mock_post.return_value = make_http_response(json_data=payload)

        client, mock_tracer, _run = self._build_client_with_mock_tracer()

        client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={}, run_name="test_run")

        mock_tracer.trace_llm_run.assert_called_once()
        call_args, call_kwargs = mock_tracer.trace_llm_run.call_args
        assert call_args[0] == "test_run"
        assert call_kwargs["metadata"] == {"ls_provider": "typesafe-ai", "ls_model_name": "jev"}

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_call_records_content_and_raw_response_on_run(self, mock_load_prompt, mock_post):
        """The tracer's run object should be updated with the resolved answer and
        the full raw response, for debugging purposes."""
        answer = {"probability": 0.5}
        payload = make_answers_payload(answer)
        mock_post.return_value = make_http_response(json_data=payload)

        client, _mock_tracer, run = self._build_client_with_mock_tracer()

        client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={}, run_name="test_run")

        run.update.assert_called_once_with({"content": answer, "raw_response": payload})


# ---------------------------------------------------------------------------
# JevClient - error handling
# ---------------------------------------------------------------------------


class TestJevClientCallErrors:

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_ask_boolean_raises_http_error_on_failed_request(self, mock_load_prompt, mock_post, jev_client):
        """A non-2xx HTTP status should propagate as requests.HTTPError."""
        mock_post.return_value = make_http_response(status_code=500, text="Internal Error")

        with pytest.raises(requests.HTTPError):
            jev_client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={})

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_ask_choice_raises_http_error_on_failed_request(self, mock_load_prompt, mock_post, jev_client):
        """Same HTTP error handling applies to ask_choice, since both question
        types share the same underlying _call."""
        mock_post.return_value = make_http_response(status_code=400, text="Bad Request")

        with pytest.raises(requests.HTTPError):
            jev_client.ask_choice(
                system_prompt_filename="dummy_prompt.md",
                full_name="Jane Doe",
                members_names=["Jane D."],
            )

    @patch("services.jev_client.requests.post")
    def test_ask_boolean_raises_file_not_found_for_missing_prompt(self, mock_post, jev_client):
        """A missing system prompt file should raise FileNotFoundError before any
        HTTP call is made."""
        with pytest.raises(FileNotFoundError):
            jev_client.ask_boolean(
                system_prompt_filename="this_prompt_does_not_exist.md",
                state={},
            )

        # The HTTP call should never happen if the prompt could not be loaded.
        mock_post.assert_not_called()

    @patch("services.jev_client.requests.post")
    def test_ask_choice_raises_file_not_found_for_missing_prompt(self, mock_post, jev_client):
        """Same prompt-loading guard applies to ask_choice."""
        with pytest.raises(FileNotFoundError):
            jev_client.ask_choice(
                system_prompt_filename="this_prompt_does_not_exist.md",
                full_name="Jane Doe",
                members_names=["Jane D."],
            )

        mock_post.assert_not_called()

    def test_ask_boolean_raises_value_error_when_model_has_no_provider_prefix(self, tracer):
        """model.split('/') expects a 'provider/model' format; a bare model name
        should fail when unpacked into (provider, model_name)."""
        client = JevClient(
            model="no-provider-model",
            url="https://fake-gateway.test/v1/evaluate",
            api_key="fake-api-key",
            tracer=tracer,
        )
        with patch.object(JevClient, "_load_system_prompt", return_value="prompt"), pytest.raises(ValueError):
            client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={})

    @patch("services.jev_client.requests.post")
    @patch.object(JevClient, "_load_system_prompt", return_value="System instructions")
    def test_ask_boolean_logs_response_body_on_error(self, mock_load_prompt, mock_post, jev_client, caplog):
        """The response body should be logged on error - it's far more useful than
        a bare status code when debugging a new/evolving API."""
        mock_post.return_value = make_http_response(status_code=422, text="Unprocessable entity detail")

        with caplog.at_level("ERROR"), pytest.raises(requests.HTTPError):
            jev_client.ask_boolean(system_prompt_filename="dummy_prompt.md", state={})

        assert "Unprocessable entity detail" in caplog.text


# ---------------------------------------------------------------------------
# JevClient._load_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:

    def test_load_system_prompt_reads_file_content(self):
        """_load_system_prompt should return the exact text content of the prompt file."""
        with patch.object(Path, "read_text", return_value="Prompt body") as mock_read_text:
            content = JevClient._load_system_prompt("some_prompt.md")

        assert content == "Prompt body"
        mock_read_text.assert_called_once_with(encoding="utf-8")

    def test_load_system_prompt_raises_when_file_missing(self):
        """A prompt filename with no matching file on disk should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            JevClient._load_system_prompt("definitely_missing_prompt_12345.md")
