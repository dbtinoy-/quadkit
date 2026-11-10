"""Typed LLM errors must map to their status codes without a cause chain.

Clients that return ``Err(LLMRateLimitError(...))`` (rather than raising
``from`` an ``HttpStatusError``) carry no ``__cause__``.  The cascade's
status extraction must still recognise them so 429s cool the entry down
and 402s exhaust it for the day.
"""

from __future__ import annotations

from quadkit.ai.llm.exceptions import (
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
)
from quadkit.ai.llm.routing.strategies.base import _extract_status_code


def test_rate_limit_error_maps_to_429_without_cause():
    assert _extract_status_code(LLMRateLimitError("throttled")) == 429


def test_quota_error_maps_to_402_without_cause():
    assert _extract_status_code(LLMQuotaExceededError("payment required")) == 402


def test_generic_llm_error_has_no_status():
    assert _extract_status_code(LLMError("boom")) is None
