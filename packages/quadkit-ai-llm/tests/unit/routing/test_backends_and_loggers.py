"""Unit tests for InMemoryQuotaBackend and InMemoryInferenceLogger."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.loggers.memory import InMemoryInferenceLogger
from quadkit.ai.llm.routing.types import InferenceLog, InferenceResult, ProviderUsage


# ── InMemoryQuotaBackend ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quota_backend_not_exhausted_by_default():
    backend = InMemoryQuotaBackend()
    assert await backend.is_exhausted("groq") is False


@pytest.mark.asyncio
async def test_quota_backend_increment_tracks_usage():
    backend = InMemoryQuotaBackend()
    await backend.increment("groq")
    await backend.increment("groq")
    usage = await backend.get_usage("groq")
    assert usage is not None
    assert usage.success_count == 2
    assert usage.error_count == 0
    assert usage.is_exhausted is False


@pytest.mark.asyncio
async def test_quota_backend_mark_exhausted():
    backend = InMemoryQuotaBackend()
    await backend.mark_exhausted("gemini")
    assert await backend.is_exhausted("gemini") is True

    # Other providers not affected
    assert await backend.is_exhausted("groq") is False


@pytest.mark.asyncio
async def test_quota_backend_record_error():
    backend = InMemoryQuotaBackend()
    await backend.record_error("cloudflare")
    usage = await backend.get_usage("cloudflare")
    assert usage is not None
    assert usage.error_count == 1
    assert usage.is_exhausted is False


@pytest.mark.asyncio
async def test_quota_backend_exhausted_after_mark_only():
    """Exhaustion is driven by explicit mark_exhausted, not by increment count."""
    backend = InMemoryQuotaBackend()
    # Many increments alone do NOT cause exhaustion
    for _ in range(100):
        await backend.increment("groq")
    assert await backend.is_exhausted("groq") is False
    # Explicit mark does
    await backend.mark_exhausted("groq")
    assert await backend.is_exhausted("groq") is True


@pytest.mark.asyncio
async def test_quota_backend_get_all_usage():
    backend = InMemoryQuotaBackend()
    await backend.increment("groq")
    await backend.increment("gemini")
    all_usage = await backend.get_all_usage()
    provider_names = {u.provider for u in all_usage}
    assert "groq" in provider_names
    assert "gemini" in provider_names


@pytest.mark.asyncio
async def test_quota_backend_get_usage_returns_none_for_unknown():
    backend = InMemoryQuotaBackend()
    result = await backend.get_usage("unknown_provider")
    assert result is None


# ── InMemoryInferenceLogger ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inference_logger_empty_by_default():
    logger = InMemoryInferenceLogger()
    entries = await logger.get_recent()
    assert entries == []


@pytest.mark.asyncio
async def test_inference_logger_stores_entries():
    logger = InMemoryInferenceLogger()
    log = InferenceLog(
        result=InferenceResult(provider="groq", model="llama-3.1-70b-versatile", content="Hello"),
        providers_tried=["groq"],
        total_attempts=1,
    )
    await logger.log(log)
    recent = await logger.get_recent()
    assert len(recent) == 1
    assert recent[0].result is not None
    assert recent[0].result.provider == "groq"


@pytest.mark.asyncio
async def test_inference_logger_newest_first():
    logger = InMemoryInferenceLogger()
    for i in range(3):
        log = InferenceLog(
            result=InferenceResult(provider=f"p{i}", model="m", content=f"c{i}"),
            providers_tried=[f"p{i}"],
            total_attempts=1,
        )
        await logger.log(log)

    recent = await logger.get_recent()
    # Newest first
    assert recent[0].result.provider == "p2"
    assert recent[1].result.provider == "p1"
    assert recent[2].result.provider == "p0"


@pytest.mark.asyncio
async def test_inference_logger_fifo_eviction():
    logger = InMemoryInferenceLogger(max_size=2)
    for i in range(3):
        log = InferenceLog(
            result=InferenceResult(provider=f"p{i}", model="m", content=f"c{i}"),
            providers_tried=[f"p{i}"],
            total_attempts=1,
        )
        await logger.log(log)

    # Only last 2 retained (p1, p2)
    recent = await logger.get_recent()
    assert len(recent) == 2
    providers = {e.result.provider for e in recent}
    assert "p0" not in providers


@pytest.mark.asyncio
async def test_inference_logger_limit_respected():
    logger = InMemoryInferenceLogger()
    for i in range(10):
        log = InferenceLog(
            result=InferenceResult(provider="groq", model="m", content=f"c{i}"),
            providers_tried=["groq"],
            total_attempts=1,
        )
        await logger.log(log)

    recent = await logger.get_recent(limit=3)
    assert len(recent) == 3
