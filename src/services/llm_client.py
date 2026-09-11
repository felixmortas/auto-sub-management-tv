"""Lightweight LLM client using an OpenAI-compatible HTTP API."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


class LLMClient:
    """Send prompts to an OpenAI-compatible LLM endpoint."""

    def __init__(
        self,
        model: str,
        url: str,
        api_key: str,
        tracer: Any,
    ) -> None:
        """Initialize the LLM client.

        Args:
            model: Model identifier sent to the API.
            url: OpenAI-compatible chat completions endpoint.
            api_key: API key used for Bearer authentication.
            tracer: Tracer exposing a ``trace_llm_run`` context manager.
        """
        self.model = model
        self.url = url
        self.api_key = api_key
        self.tracer = tracer

    def call(
        self,
        system_prompt_filename: str,
        user_message: str,
        *,
        run_name: str = "llm_call",
        parse_json: bool = True,
    ) -> Any:
        """Call the LLM and return its content.

        Args:
            system_prompt_filename: Prompt filename located in the prompts directory.
            user_message: User message sent to the model.
            run_name: Name used for the tracing run.
            parse_json: Whether to parse the assistant content as JSON.

        Returns:
            Parsed JSON when ``parse_json`` is True, otherwise the raw text content.

        Raises:
            FileNotFoundError: If the system prompt file does not exist.
            requests.RequestException: If the HTTP request fails.
            KeyError: If the API response does not contain the expected fields.
            json.JSONDecodeError: If JSON parsing is requested but the model response
                is not valid JSON.
        """
        system_prompt = self._load_system_prompt(system_prompt_filename)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        if parse_json:
            # Ask the API to constrain the model response to a JSON object.
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        with self.tracer.trace_llm_run(run_name, payload) as run:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            usage = self._normalize_usage(result.get("usage"))
            parsed_data = json.loads(content)

            run["output"] = parsed_data

            return parsed_data

    @staticmethod
    def normalize_bool(value: Any) -> Any:
        """Normalize common string boolean representations.

        Args:
            value: Value to normalize.

        Returns:
            A boolean for recognized string representations, otherwise the
            original value.
        """
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False

        return value

    @staticmethod
    def normalize_int(value: Any) -> Any:
        """Normalize integer-like strings without coercing unrelated values.

        Args:
            value: Value to normalize.

        Returns:
            An integer when the value is an integer-like string, otherwise the
            original value.
        """
        if isinstance(value, str):
            normalized = value.strip()

            try:
                return int(normalized)
            except ValueError:
                return value

        return value

    @staticmethod
    def _normalize_usage(usage: dict | None) -> dict | None:
        """Normalize token usage into LangSmith's expected format."""
        if not usage:
            return None

        input_tokens = usage.get(
            "input_tokens",
            usage.get("prompt_tokens"),
        )
        output_tokens = usage.get(
            "output_tokens",
            usage.get("completion_tokens"),
        )
        total_tokens = usage.get("total_tokens")

        if input_tokens is None and output_tokens is None:
            return None

        input_tokens = input_tokens or 0
        output_tokens = output_tokens or 0

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (
                total_tokens
                if total_tokens is not None
                else input_tokens + output_tokens
            ),
        }

    @staticmethod
    def _extract_content(result: dict) -> str:
        """Extract assistant content from a supported API response."""
        if "choices" in result:
            return result["choices"][0]["message"]["content"]

        if "output_text" in result:
            return result["output_text"]

        raise ValueError("Unsupported LLM response format")

    @staticmethod
    def _load_system_prompt(system_prompt_filename: str) -> str:
        """Load a system prompt from the project's prompts directory.

        Args:
            system_prompt_filename: Prompt filename located in the prompts directory.

        Returns:
            Prompt file content.
        """
        prompt_path = (
            Path(__file__).resolve().parent
            / ".."
            / "prompts"
            / system_prompt_filename
        ).resolve()

        return prompt_path.read_text(encoding="utf-8")
