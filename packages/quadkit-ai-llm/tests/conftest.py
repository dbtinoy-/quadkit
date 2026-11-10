"""Shared test configuration and fixtures."""

from __future__ import annotations

import os
from pathlib import Path
import sys

# Allow absolute imports like 'from support.mock_clients import ...'
sys.path.insert(0, str(Path(__file__).parent))

import pytest

from quadkit.ai.llm.registry.core import ProviderRegistry


@pytest.fixture(scope="module", autouse=True)
def _setup_test_env() -> None:
    """Set up test environment variables that are required for test fixtures.

    This fixture runs per test module and sets up environment variables
    needed by LLM client initialization during tests. The key is restored
    on teardown so it never leaks into other packages' tests.
    """
    # Set a dummy OpenAI API key for test fixture initialization
    # Tests that need specific keys or mocking should override this
    _previous = os.environ.get("OPENAI_API_KEY")
    if not _previous:
        os.environ["OPENAI_API_KEY"] = "sk-test-key-for-fixtures"
    yield
    if _previous is None:
        os.environ.pop("OPENAI_API_KEY", None)
    else:
        os.environ["OPENAI_API_KEY"] = _previous


@pytest.fixture
def provider_registry() -> ProviderRegistry:
    """Provide a fresh ProviderRegistry instance for each test.

    Returns:
        A new ProviderRegistry with all built-in providers registered.
    """
    return ProviderRegistry.with_defaults()


class _FakeEncoding:
    """Deterministic stand-in for a tiktoken encoding.

    The real encoders are fetched from the network on first use, which a unit
    test must not depend on: one token per whitespace-separated word keeps the
    counters' arithmetic observable without a download.
    """

    def encode(self, text: str) -> list[int]:
        """Tokenize on whitespace.

        Args:
            text: Text to tokenize.

        Returns:
            One token id per whitespace-separated word.
        """
        return list(range(len(text.split())))


@pytest.fixture
def fake_tiktoken(monkeypatch: pytest.MonkeyPatch) -> _FakeEncoding:
    """Serve every tiktoken encoder from the local stub.

    Args:
        monkeypatch: Patch handle for the tiktoken module attributes.

    Returns:
        The encoding the patched lookups hand back.
    """
    import tiktoken

    encoding = _FakeEncoding()
    monkeypatch.setattr(tiktoken, "encoding_for_model", lambda *_: encoding)
    monkeypatch.setattr(tiktoken, "get_encoding", lambda *_: encoding)
    return encoding
