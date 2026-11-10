"""Domain events for quadkit-ai-llm — immutable facts emitted when completions occur.

These events are published through EventBusProtocol and consumed by
cost accounting, audit, and safety review systems.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "LLMCompletionEvent",
]


@dataclass(frozen=True, init=False)
class LLMCompletionEvent(DomainEvent):
    """Emitted when an LLM completion is received.

    Distinct from LLMCallStartedHook (which intercepts); this is the
    immutable record that a completion happened.

    Consumed by: cost accounting, audit, safety review.
    """

    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
