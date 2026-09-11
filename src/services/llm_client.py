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

        provider, model_name = self.model.split("/")

        with self.tracer.trace_llm_run(run_name, payload, metadata={"ls_provider": provider, "ls_model_name": model_name}) as run:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Only decode the content as JSON when explicitly requested. Otherwise,
            # return the raw text exactly as the model produced it.
            parsed_data = json.loads(content) if parse_json else content

            run.update(self._build_run_data(result, parsed_data))

            return parsed_data

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

    @staticmethod
    def _build_run_data(result: dict[str, Any], parsed_data: Any) -> dict[str, Any]:
        message = result["choices"][0]["message"]
        usage = result.get("usage", {})

        total_output_tokens = usage.get("completion_tokens", 0)
        reasoning_tokens = (
            usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        )

        return {
            "reasoning": message.get("reasoning"),
            "content": parsed_data,
            "usage_metadata": {
                "total_tokens": usage.get("total_tokens"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "reasoning_tokens": reasoning_tokens,
                "completion_tokens": total_output_tokens - reasoning_tokens,
                "total_output_tokens": total_output_tokens,
                "cost": usage.get("cost"),
            },
        }