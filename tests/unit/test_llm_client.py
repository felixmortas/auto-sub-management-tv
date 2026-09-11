"""
Unit tests for LLMClient.

Most tests use the shared `tracer` fixture (a real LangSmithTracer, explicitly
disabled - see conftest.py), which exercises the same code path as production
without making network calls. The couple of tests that need to inspect what
LLMClient actually writes onto the run object build a local
MagicMock(spec=LangSmithTracer) instead, as recommended by that fixture's
docstring.

Run with:
    pytest test_llm_client.py -v
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.langsmith_tracer import LangSmithTracer
from services.llm_client import LLMClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_http_response(status_code=200, json_data=None, text=""):
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


def make_api_payload(
    content,
    reasoning="Some reasoning trace",
    total_tokens=100,
    prompt_tokens=60,
    completion_tokens_total=40,
    reasoning_tokens=10,
    cost=0.002,
):
    """Build a fake OpenAI-compatible chat completion response body.

    `content` is expected to already be a JSON-serialized string (or plain
    text, for parse_json=False scenarios), exactly as the real API returns
    it in `choices[0].message.content`.
    """
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "reasoning": reasoning,
                }
            }
        ],
        "usage": {
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens_total,
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
            "cost": cost,
        },
    }


@pytest.fixture
def llm_client(tracer):
    """Build an LLMClient wired to the shared (disabled) tracer fixture."""
    return LLMClient(
        model="deepseek/deepseek-v4-flash-0731",
        url="https://fake-gateway.test/v1/chat/completions",
        api_key="fake-api-key",
        tracer=tracer,
    )


# ---------------------------------------------------------------------------
# LLMClient.call - happy path
# ---------------------------------------------------------------------------


class TestLLMClientCallSuccess:

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="You are a helpful assistant.")
    def test_call_returns_parsed_json(self, mock_load_prompt, mock_post, llm_client):
        """call() should parse and return the JSON content of the response by default."""
        payload = make_api_payload(content=json.dumps({"answer": 42}))
        mock_post.return_value = make_http_response(json_data=payload)

        result = llm_client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="What is the answer?",
            run_name="test_run",
        )

        assert result == {"answer": 42}

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt content")
    def test_call_sends_correct_request_payload(self, mock_load_prompt, mock_post, llm_client):
        """The HTTP request should carry the model, both messages, and the auth header."""
        payload = make_api_payload(content=json.dumps({"ok": True}))
        mock_post.return_value = make_http_response(json_data=payload)

        llm_client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hello there",
            run_name="test_run",
        )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args

        assert kwargs["headers"]["Authorization"] == "Bearer fake-api-key"
        assert kwargs["headers"]["Content-Type"] == "application/json"
        assert kwargs["json"]["model"] == "deepseek/deepseek-v4-flash-0731"
        assert kwargs["json"]["messages"][0] == {
            "role": "system",
            "content": "System prompt content",
        }
        assert kwargs["json"]["messages"][1] == {
            "role": "user",
            "content": "Hello there",
        }
        # response_format should be forced to JSON mode by default (parse_json=True).
        assert kwargs["json"]["response_format"] == {"type": "json_object"}

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt content")
    def test_call_omits_response_format_when_parse_json_false(self, mock_load_prompt, mock_post, llm_client):
        """When parse_json=False, the request should not force JSON-mode output."""
        payload = make_api_payload(content="Some free-form text answer.")
        mock_post.return_value = make_http_response(json_data=payload)

        llm_client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hello",
            run_name="test_run",
            parse_json=False,
        )

        _, kwargs = mock_post.call_args
        assert "response_format" not in kwargs["json"]

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt content")
    def test_call_returns_raw_text_when_parse_json_false(self, mock_load_prompt, mock_post, llm_client):
        """With parse_json=False, the raw text content should be returned untouched,
        even when it is not valid JSON."""
        payload = make_api_payload(content="Some free-form text answer, not JSON at all.")
        mock_post.return_value = make_http_response(json_data=payload)

        result = llm_client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hello",
            run_name="test_run",
            parse_json=False,
        )

        assert result == "Some free-form text answer, not JSON at all."

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt content")
    def test_call_returns_raw_string_when_parse_json_false_even_if_content_looks_like_json(
        self, mock_load_prompt, mock_post, llm_client
    ):
        """parse_json=False just skips decoding; if the model happens to answer with
        a JSON-looking string anyway, it is returned as that raw string, not a dict."""
        payload = make_api_payload(content=json.dumps({"still": "a string here"}))
        mock_post.return_value = make_http_response(json_data=payload)

        result = llm_client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hello",
            run_name="test_run",
            parse_json=False,
        )

        assert result == '{"still": "a string here"}'
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# LLMClient.call - usage metadata & tracing
#
# These tests build a dedicated LLMClient with a local MagicMock(spec=LangSmithTracer)
# instead of using the shared `tracer` fixture, specifically to inspect the run
# object that LLMClient writes to.
# ---------------------------------------------------------------------------


class TestLLMClientTracing:

    def _build_client_with_mock_tracer(self):
        """Build an LLMClient plus a mock tracer whose yielded run is a real dict,
        so writes to it (run["key"] = value) can be asserted on afterwards."""
        mock_tracer = MagicMock(spec=LangSmithTracer)
        run: dict = {}
        mock_tracer.trace_llm_run.return_value.__enter__.return_value = run

        client = LLMClient(
            model="deepseek/deepseek-v4-flash-0731",
            url="https://fake-gateway.test/v1/chat/completions",
            api_key="fake-api-key",
            tracer=mock_tracer,
        )
        return client, mock_tracer, run

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt")
    def test_call_computes_completion_tokens_excluding_reasoning(self, mock_load_prompt, mock_post):
        """completion_tokens should be total_output_tokens minus reasoning_tokens,
        and the provider/model split should be forwarded as tracer metadata."""
        payload = make_api_payload(
            content=json.dumps({"ok": True}),
            completion_tokens_total=40,
            reasoning_tokens=15,
        )
        mock_post.return_value = make_http_response(json_data=payload)

        client, mock_tracer, run = self._build_client_with_mock_tracer()

        client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hi",
            run_name="test_run",
        )

        mock_tracer.trace_llm_run.assert_called_once()
        call_args, call_kwargs = mock_tracer.trace_llm_run.call_args
        assert call_args[0] == "test_run"
        assert call_kwargs["metadata"] == {"ls_provider": "deepseek", "ls_model_name": "deepseek-v4-flash-0731"}

        assert run["usage_metadata"]["reasoning_tokens"] == 15
        assert run["usage_metadata"]["total_output_tokens"] == 40
        assert run["usage_metadata"]["completion_tokens"] == 25

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt")
    def test_call_records_reasoning_and_content_on_run(self, mock_load_prompt, mock_post):
        """The tracer's run dict should be enriched with reasoning, content and usage."""
        payload = make_api_payload(content=json.dumps({"value": 1}), reasoning="Because 1 is 1")
        mock_post.return_value = make_http_response(json_data=payload)

        client, _mock_tracer, run = self._build_client_with_mock_tracer()

        client.call(
            system_prompt_filename="dummy_prompt.md",
            user_message="Hi",
            run_name="test_run",
        )

        assert run["reasoning"] == "Because 1 is 1"
        assert run["content"] == {"value": 1}
        assert "usage_metadata" in run


# ---------------------------------------------------------------------------
# LLMClient.call - error handling
# ---------------------------------------------------------------------------


class TestLLMClientCallErrors:

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt")
    def test_call_raises_http_error_on_failed_request(self, mock_load_prompt, mock_post, llm_client):
        """A non-2xx HTTP status should propagate as requests.HTTPError."""
        mock_post.return_value = make_http_response(status_code=500, text="Internal Error")

        with pytest.raises(requests.HTTPError):
            llm_client.call(
                system_prompt_filename="dummy_prompt.md",
                user_message="Hi",
                run_name="test_run",
            )

    @patch("services.llm_client.requests.post")
    @patch.object(LLMClient, "_load_system_prompt", return_value="System prompt")
    def test_call_raises_json_decode_error_on_invalid_content(self, mock_load_prompt, mock_post, llm_client):
        """Non-JSON content should raise JSONDecodeError when parse_json is True (default)."""
        payload = make_api_payload(content="This is not JSON")
        mock_post.return_value = make_http_response(json_data=payload)

        with pytest.raises(json.JSONDecodeError):
            llm_client.call(
                system_prompt_filename="dummy_prompt.md",
                user_message="Hi",
                run_name="test_run",
            )

    @patch("services.llm_client.requests.post")
    def test_call_raises_file_not_found_for_missing_prompt(self, mock_post, llm_client):
        """A missing system prompt file should raise FileNotFoundError before any HTTP call."""
        with pytest.raises(FileNotFoundError):
            llm_client.call(
                system_prompt_filename="this_prompt_does_not_exist.md",
                user_message="Hi",
                run_name="test_run",
            )

        # The HTTP call should never happen if the prompt could not be loaded.
        mock_post.assert_not_called()

    def test_call_raises_value_error_when_model_has_no_provider_prefix(self, tracer):
        """model.split('/') expects a 'provider/model' format; a bare model name should fail
        when unpacked into (provider, model_name)."""
        client = LLMClient(
            model="no-provider-model",
            url="https://fake-gateway.test/v1/chat/completions",
            api_key="fake-api-key",
            tracer=tracer,
        )
        with patch.object(LLMClient, "_load_system_prompt", return_value="prompt"), pytest.raises(ValueError):
            client.call(
                system_prompt_filename="dummy_prompt.md",
                user_message="Hi",
                run_name="test_run",
            )


# ---------------------------------------------------------------------------
# LLMClient._load_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:

    def test_load_system_prompt_reads_file_content(self):
        """_load_system_prompt should return the exact text content of the prompt file."""
        with patch.object(Path, "read_text", return_value="Prompt body") as mock_read_text:
            content = LLMClient._load_system_prompt("some_prompt.md")

        assert content == "Prompt body"
        mock_read_text.assert_called_once_with(encoding="utf-8")

    def test_load_system_prompt_raises_when_file_missing(self):
        """A prompt filename with no matching file on disk should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            LLMClient._load_system_prompt("definitely_missing_prompt_12345.md")
