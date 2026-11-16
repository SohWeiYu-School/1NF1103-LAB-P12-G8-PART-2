"""Shared pytest fixtures."""

import logging

import pytest


@pytest.fixture(autouse=True)
def _no_real_api_keys(monkeypatch):
    """Tests never call the real AI. main.py loads .env, so on a computer with real keys in .env the
    tests would otherwise call OpenAI (costing money) and get different answers than everyone else.
    A test that needs a key sets a fake one itself with monkeypatch.setenv."""
    for name in ("OPENAI_API_KEY", "OPEN_AI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _suppress_console_logging():
    """Prevent any log records from reaching the console during tests."""
    root = logging.getLogger()
    null = logging.NullHandler()
    root.addHandler(null)
    # Remove any StreamHandlers that may have been added before the test
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, logging.FileHandler)]
    for h in stream_handlers:
        root.removeHandler(h)
    yield
    root.removeHandler(null)

TEST_AUDIT_KEY = "0123456789abcdef" * 4        # 64 hex characters, only ever used by the tests


@pytest.fixture(autouse=True)
def _audit_key(monkeypatch):
    """The audit log is signed with AUDIT_KEY, and App refuses to start without one. Every test gets the
    same fixed key; a test about a missing key deletes it itself."""
    monkeypatch.setenv("AUDIT_KEY", TEST_AUDIT_KEY)
