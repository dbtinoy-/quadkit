"""Tests for per-entry cascade identity and cooldown configuration.

Multiple cascade entries may share a provider ``name`` (e.g. several
OpenRouter models).  All routing state — clients, quota, exhaustion —
must key on ``ProviderConfig.key`` (``name:model``), never on ``name``,
so one entry's failure cannot poison its siblings.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    LLMConfig,
    ProviderConfig,
    QuotaConfig,
)
from quadkit.ai.llm.routing.di_factories import create_routing_clients
from quadkit.ai.llm.routing.strategies.sequential import SequentialCascadeStrategy
from quadkit.ai.llm.types import AIError, Completion
from quadkit.result import Err, Ok


def test_provider_key_combines_name_and_model():
    p = ProviderConfig(name="openrouter", model="google/gemma-4-31b-it:free")
    assert p.key == "openrouter:google/gemma-4-31b-it:free"


def test_provider_keys_distinct_for_same_name():
    a = ProviderConfig(name="openrouter", model="m1")
    b = ProviderConfig(name="openrouter", model="m2")
    assert a.key != b.key


def test_quota_config_cooldown_default():
    assert QuotaConfig().cooldown_seconds == 300


# ── Per-entry clients ────────────────────────────────────────────────────────


def test_create_routing_clients_builds_one_client_per_entry():
    config = LLMConfig(
        providers=[
            ProviderConfig(name="openrouter", model="m1", api_key="fake"),
            ProviderConfig(name="openrouter", model="m2", api_key="fake"),
        ],
    )
    clients = create_routing_clients(config)
    assert set(clients) == {"openrouter:m1", "openrouter:m2"}
    assert clients["openrouter:m1"] is not clients["openrouter:m2"]


# ── Cascade behavior across same-name entries ────────────────────────────────


class _StatusError(AIError):
    """AIError carrying an HTTP status code, as real client errors do."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class _StubClient:
    """Minimal LLM client stub: returns a fixed Result from complete()."""

    def __init__(self, result) -> None:
        self._result = result
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        return self._result


def _completion(text: str = "ok") -> Completion:
    return Completion(content=text, model="test-model", usage=None)


def _two_entry_config(cooldown_seconds: int = 300) -> LLMConfig:
    return LLMConfig(
        providers=[
            ProviderConfig(name="openrouter", model="m1", api_key="fake"),
            ProviderConfig(name="openrouter", model="m2", api_key="fake"),
        ],
        quota=QuotaConfig(cooldown_seconds=cooldown_seconds),
    )


async def test_429_on_first_entry_advances_to_second():
    quota = InMemoryQuotaBackend()
    config = _two_entry_config()
    clients = {
        "openrouter:m1": _StubClient(Err(_StatusError("throttled", 429))),
        "openrouter:m2": _StubClient(Ok(_completion("from-m2"))),
    }

    result, tried, attempts = await SequentialCascadeStrategy().execute(
        providers=config.providers,
        clients=clients,
        quota=quota,
        config=config,
        messages=[{"role": "user", "content": "hi"}],
        kwargs={},
    )

    assert result is not None and result.content == "from-m2"
    assert attempts == 2
    assert await quota.is_exhausted("openrouter:m1") is True
    assert await quota.is_exhausted("openrouter:m2") is False


async def test_429_cooldown_uses_config_cooldown_seconds():
    quota = InMemoryQuotaBackend()
    config = _two_entry_config(cooldown_seconds=60)
    clients = {
        "openrouter:m1": _StubClient(Err(_StatusError("throttled", 429))),
        "openrouter:m2": _StubClient(Ok(_completion())),
    }

    before = datetime.now(UTC)
    await SequentialCascadeStrategy().execute(
        providers=config.providers,
        clients=clients,
        quota=quota,
        config=config,
        messages=[{"role": "user", "content": "hi"}],
        kwargs={},
    )

    usage = await quota.get_usage("openrouter:m1")
    assert usage is not None and usage.exhausted_until is not None
    delta = usage.exhausted_until - before
    assert timedelta(seconds=55) < delta < timedelta(seconds=65)


async def test_402_marks_exhausted_until_end_of_day():
    quota = InMemoryQuotaBackend()
    config = _two_entry_config(cooldown_seconds=60)
    clients = {
        "openrouter:m1": _StubClient(Err(_StatusError("payment required", 402))),
        "openrouter:m2": _StubClient(Ok(_completion())),
    }

    await SequentialCascadeStrategy().execute(
        providers=config.providers,
        clients=clients,
        quota=quota,
        config=config,
        messages=[{"role": "user", "content": "hi"}],
        kwargs={},
    )

    usage = await quota.get_usage("openrouter:m1")
    assert usage is not None and usage.exhausted_until is not None
    # End of UTC day: later than any short cooldown, at most 24h away.
    delta = usage.exhausted_until - datetime.now(UTC)
    assert timedelta(minutes=5) < delta <= timedelta(hours=24)
