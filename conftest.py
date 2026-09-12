# conftest.py

"""
Makes the project root importable for pytest, regardless of how pytest
is invoked (`pytest ...`, `python -m pytest ...`, an IDE's test
runner, etc.).

Without this, `pytest tests/test_api_review_endpoints.py` fails with
"ModuleNotFoundError: No module named 'api'" — pytest only adds the
tests/ folder itself to sys.path by default (since it has no
__init__.py), not the project root one level up.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest


@pytest.fixture(autouse=True)
def _no_real_api_key(monkeypatch):
    """
    Force the mock analyzer path in every test by removing the API key
    from the environment for the test's duration. Without this, the
    items-endpoint tests make real (paid, slow, non-deterministic)
    Claude calls whenever a developer has a key in .env — which the
    llm_calls.log trace lines revealed was actually happening.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)