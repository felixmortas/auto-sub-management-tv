"""
Shared pytest fixtures for the test suite.

Fixtures defined here are auto-discovered by pytest for every test file
in this directory (and subdirectories) — no import needed in the test
files themselves.
"""

import pathlib

import pytest

from services.langsmith_tracer import LangSmithTracer


def pytest_collection_modifyitems(items):
    """Auto-tag each test with 'unit' or 'integration' based on its folder
    (tests/unit/ vs tests/integration/), so `-m unit` / `-m integration`
    work without needing a `pytestmark` line in every single test file.
    Tests already carrying an explicit marker (e.g. via pytestmark) simply
    get it added again, which is a harmless no-op.
    """
    for item in items:
        parts = pathlib.Path(str(item.fspath)).parts
        if "unit" in parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in parts:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def tracer():
    """
    A real LangSmithTracer instance, explicitly disabled.

    Using the real class (rather than a bare MagicMock) exercises the exact
    same code path as production — the context manager, the try/except
    around network calls — without making any HTTP request. This is the
    right default for most tests: they exist to check business logic, not
    tracing behavior.

    For tests that specifically need to assert tracing behavior (e.g. "was
    end_run called with an error"), build a MagicMock(spec=LangSmithTracer)
    locally in that test instead of using this fixture.
    """
    return LangSmithTracer(enabled=False)
