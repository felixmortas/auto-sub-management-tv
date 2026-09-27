"""Client for the Jev evaluation model (typesafe-ai/jev), served via the
Vercel AI Gateway.

Jev is NOT an OpenAI-compatible chat model: instead of "messages", it expects
a `state` (the data being evaluated) and a set of `questions`, each with its
own `type` ("boolean", "choice", ...) and `instructions`. The response is
returned under `answers.<question_key>` instead of `choices[0].message`.

This client is deliberately agnostic to the question's key name: since each
request only ever sends a single question, the answer is read back as "the
one and only value in `answers`", regardless of how that key is spelled.
Callers never need to know or pass a question key.

Both question types ("noul"/boolean and "choice") share the
same HTTP call, tracing and error-handling logic, so they live in a single
class with one dedicated method per question type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JevChoiceResult:
    """Result of a 'choice' question, already resolved against the original
    candidate names (instead of the internal "member_0", "member_1", ...
    keys used as stable identifiers in the request).
    """

    choice: str  # candidate name Jev selected
    probabilities: dict[str, float]  # candidate name -> probability
    confidence: float
    raw_answer: dict[str, Any]  # kept for debugging / future needs


class JevClient:
    """Send 'boolean' and 'choice' evaluation questions to a Jev model."""

    # Arbitrary key used internally to name the single question sent in each
    # request. Its value is never exposed to callers: the answer is always
    # read back as the sole entry of `answers`, whatever its key is.
    _QUESTION_KEY = "question"

    def __init__(
        self,
        model: str,
        url: str,
        api_key: str,
        tracer: Any,
        timeout: int = 120,
    ) -> None:
        """Initialize the Jev client.

        Args:
            model: Jev model identifier, e.g. "typesafe-ai/jev".
            url: AI Gateway evaluate endpoint.
            api_key: API key used for Bearer authentication.
            tracer: Tracer exposing a ``trace_llm_run`` context manager
                (same interface as the one used by LLMClient).
            timeout: HTTP request timeout, in seconds.
        """
        self.model = model
        self.url = url
        self.api_key = api_key
        self.tracer = tracer
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask_boolean(
        self,
        system_prompt_filename: str,
        state: Any,
        *,
        run_name: str = "jev_boolean_call",
    ) -> float:
        """Ask a yes/no ('noul') question about the given state.

        Args:
            system_prompt_filename: Prompt filename in the prompts directory,
                used as the question's `instructions`.
            state: Arbitrary JSON-serializable data Jev evaluates
                (e.g. a dict with the full name and the candidate names).
            run_name: Name used for the tracing run.

        Returns:
            The probability (0-1) that Jev assigned to a "true" answer.
        """
        instructions = self._load_system_prompt(system_prompt_filename)

        payload: dict[str, Any] = {
            "model": self.model,
            "state": state,
            "questions": {
                self._QUESTION_KEY: {
                    "type": "boolean",
                    "instructions": instructions,
                }
            },
        }

        answer = self._call(payload, run_name=run_name)

        return answer["probability"]

    def ask_choice(
        self,
        system_prompt_filename: str,
        full_name: str,
        members_names: list[str],
        *,
        run_name: str = "jev_choice_call",
    ) -> JevChoiceResult:
        """Ask Jev to pick which candidate matches `full_name`.

        Args:
            system_prompt_filename: Prompt filename in the prompts directory,
                used as the question's `instructions`.
            full_name: The name to match against the candidates.
            members_names: Candidate names Jev must choose from.
            run_name: Name used for the tracing run.

        Returns:
            A JevChoiceResult with the selected candidate name, the
            probability distribution over candidate names, and Jev's
            confidence.
        """
        instructions = self._load_system_prompt(system_prompt_filename)

        # Stable identifiers are used as criteria keys (rather than the names
        # themselves) to avoid issues with special characters in names. They
        # are resolved back to the original names below, once Jev answers.
        criteria = {
            f"member_{index}": member_name
            for index, member_name in enumerate(members_names)
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "state": full_name,
            "questions": {
                self._QUESTION_KEY: {
                    "type": "choice",
                    "instructions": instructions,
                    "criteria": criteria,
                }
            },
        }

        answer = self._call(payload, run_name=run_name)

        # Resolve the "member_x" keys back to the original candidate names.
        # `criteria.get(key, key)` falls back to the raw key if it's ever
        # missing, so an unexpected key never crashes the caller.
        resolved_choice = criteria.get(answer["choice"], answer["choice"])
        resolved_probabilities = {
            criteria.get(key, key): probability
            for key, probability in answer.get("probabilities", {}).items()
        }

        return JevChoiceResult(
            choice=resolved_choice,
            probabilities=resolved_probabilities,
            confidence=answer["confidence"],
            raw_answer=answer,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call(self, payload: dict[str, Any], *, run_name: str) -> dict[str, Any]:
        """Perform the HTTP call to Jev, with tracing and error handling.

        Args:
            payload: Full request body (model, state, questions).
            run_name: Name used for the tracing run.

        Returns:
            The sole value found in the response's `answers` dict, whatever
            its key is named.

        Raises:
            requests.HTTPError: If the API returns a non-2xx response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        provider, model_name = self.model.split("/")

        with self.tracer.trace_llm_run(
            run_name,
            payload,
            metadata={"ls_provider": provider, "ls_model_name": model_name},
        ) as run:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            if not response.ok:
                # Log the response body: it's far more useful than a bare
                # "400 Bad Request" for debugging a new/evolving API.
                logger.error(
                    "Jev API error (status=%s): %s",
                    response.status_code,
                    response.text,
                )
                response.raise_for_status()

            result = response.json()
            answers = result.get("answers", {})

            # Read back the single answer regardless of its question key:
            # we never need to know the name we picked when building the
            # request.
            answer = next(iter(answers.values()), None)

            run.update(
                {
                    "content": answer,
                    "raw_response": result,
                }
            )

            return answer

    @staticmethod
    def _load_system_prompt(system_prompt_filename: str) -> str:
        """Load a system prompt from the project's prompts directory.

        Args:
            system_prompt_filename: Prompt filename located in the prompts
                directory.

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