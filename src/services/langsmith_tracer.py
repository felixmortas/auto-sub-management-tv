"""
LangSmith tracing via the raw REST API (no `langsmith` SDK dependency).

Why this design:
- AWS Lambda freezes the execution environment right after the handler
  returns, so a detached background thread sending traces could be killed
  mid-flight. All tracing HTTP calls are therefore synchronous so they finish (or fail fast) within the handler's lifetime.
- Tracing must NEVER break the actual business logic (email parsing).
  Every network call to LangSmith is wrapped in try/except and only logged
  at debug level on failure.
- Tracing is auto-disabled if no API key is configured (e.g. local dev),
  so you don't need an `if os.environ.get(...)` everywhere in your code.

Reference: LangSmith "Trace with the API" docs
(https://docs.langchain.com/langsmith/trace-with-api.md), "Basic tracing"
section. With this approach (as opposed to the batch /runs/multipart
endpoint), trace_id and dotted_order are generated server-side, so we
don't need to compute them ourselves.

Note: LangSmith recommends UUIDv7 for run IDs (it embeds a timestamp,
which keeps runs correctly time-ordered in the UI). We use uuid.uuid4()
here to avoid an extra dependency; swap in a uuid7 generator if you want
that ordering guarantee.
"""

import contextlib
import datetime
import logging
import uuid

import requests

logger = logging.getLogger(__name__)


class LangSmithTracer:
    """Minimal LangSmith tracer using only the REST API."""

    def __init__(
        self, api_key=None, project=None, workspace_id=None, endpoint=None,
        enabled=None,
    ):
        self.api_key = api_key
        self.project = project
        self.workspace_id = workspace_id    # Only if API key is configured for all workspaces from the organization
        self.endpoint = (endpoint or "https://eu.api.smith.langchain.com").rstrip("/")
        # Silently no-op if no key is set, unless explicitly forced via `enabled`
        self.enabled = enabled if enabled is not None else bool(self.api_key)

    def _headers(self):
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        if self.workspace_id:
            headers["x-tenant-id"] = self.workspace_id
        return headers

    @staticmethod
    def _now_iso():
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def start_run(self, name, run_type, inputs, run_id=None, parent_run_id=None, extra=None):
        """Create a run in LangSmith. Returns the run_id (or None if disabled/failed)."""
        if not self.enabled:
            return None

        run_id = run_id or str(uuid.uuid4())
        # trace_id / dotted_order are intentionally NOT set here: for basic
        # tracing (POST /runs + PATCH /runs), LangSmith computes them
        # server-side based on parent_run_id.
        payload = {
            "id": run_id,
            "name": name,
            "run_type": run_type,  # "llm", "chain", "tool", ...
            "inputs": inputs,
            "start_time": self._now_iso(),
            "session_name": self.project,  # LangSmith "project" == "session" in the API
        }
        if parent_run_id:
            payload["parent_run_id"] = parent_run_id

        if extra:
            payload["extra"] = extra

        try:
            response = requests.post(
                f"{self.endpoint}/runs",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            # Tracing failure must never break the caller's pipeline
            logger.debug("LangSmith start_run failed: %s", e)

        return run_id

    def end_run(self, run_id, outputs=None, error=None):
        """Close a run, optionally with outputs or an error message."""
        if not self.enabled or not run_id:
            return

        payload = {"end_time": self._now_iso()}
        if outputs is not None:
            payload["outputs"] = outputs
        if error is not None:
            payload["error"] = str(error)

        try:
            response = requests.patch(
                f"{self.endpoint}/runs/{run_id}",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.debug("LangSmith end_run failed: %s", e)

    @contextlib.contextmanager
    def trace_llm_run(self, name, inputs, run_type="llm", metadata = None):
        """
        Context manager wrapping a single LLM call.

        Usage:
            with tracer.trace_llm_run("parse_email", {"content": email_content}) as run:
                ... do the LLM call ...
                run["output"] = parsed_data   # fill this dict before the block exits

        On exception, the run is closed with the error and the exception is re-raised.
        """
        run_id = self.start_run(name=name, run_type=run_type, inputs=inputs, extra={"metadata": metadata})
        outputs = {}
        try:
            yield outputs
            self.end_run(run_id, outputs=outputs)
        except Exception as e:
            self.end_run(run_id, error=e)
            raise
