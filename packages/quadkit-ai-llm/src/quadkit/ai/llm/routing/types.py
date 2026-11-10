"""Domain types for LLM multi-provider routing results and errors.

All types use the ``@dataclass(init=False)`` + ``DomainModel`` pattern
consistent with the rest of ``quadkit-ai-llm``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
import uuid

from quadkit.domain import DomainModel
from quadkit.validation import Field

__all__ = [
    "InferenceError",
    "InferenceLog",
    "InferenceResult",
    "ProviderUsage",
]


@dataclass(init=False)
class InferenceResult(DomainModel):
    """Successful result of a single provider inference attempt.

    Example:
        >>> result = InferenceResult(
        ...     provider="groq",
        ...     model="llama-3.1-70b-versatile",
        ...     content="Hello!",
        ...     attempt=1,
        ... )
    """

    provider: str = Field(description="Provider that produced this completion.")
    model: str = Field(description="Model identifier used for this attempt.")
    content: str = Field(description="Generated completion text.")
    attempt: int = Field(
        default=1, ge=1, description="Attempt number (1 = first provider tried)."
    )
    prompt_tokens: int = Field(default=0, ge=0, description="Input token count.")
    completion_tokens: int = Field(default=0, ge=0, description="Output token count.")
    is_paid: bool = Field(
        default=False, description="Whether the request was paid or used free quota."
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Round-trip latency in milliseconds.",
    )


@dataclass(init=False)
class InferenceError(DomainModel):
    """Terminal failure after all providers were exhausted.

    Example:
        >>> error = InferenceError(
        ...     message="All providers exhausted",
        ...     providers_tried=["groq", "gemini"],
        ...     last_status_code=429,
        ... )
    """

    message: str = Field(description="Human-readable failure summary.")
    providers_tried: list[str] = Field(
        default_factory=list,
        description="Ordered list of providers attempted before giving up.",
    )
    last_status_code: int | None = Field(
        default=None,
        description="HTTP status code from the last failed attempt.",
    )


@dataclass(init=False)
class InferenceLog(DomainModel):
    """Complete record of one routing run — stored by ``InferenceLoggerProtocol``.

    Contains the successful result (or a terminal error) together with the
    full provider attempt trail for observability.

    Example:
        >>> log = InferenceLog(
        ...     routing_id=uuid.uuid4(),
        ...     result=InferenceResult(provider="groq", model="llama-3.1-70b-versatile", content="Hello!"),
        ...     providers_tried=["gemini", "groq"],
        ...     total_attempts=2,
        ... )
    """

    routing_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this routing run.",
    )
    result: InferenceResult | None = Field(
        default=None,
        description="Successful completion result, or ``None`` on total failure.",
    )
    error: InferenceError | None = Field(
        default=None,
        description="Terminal error when all providers failed.",
    )
    providers_tried: list[str] = Field(
        default_factory=list,
        description="All providers attempted (including those exhausted at quota check).",
    )
    total_attempts: int = Field(
        default=0,
        ge=0,
        description="Number of actual HTTP calls made (quota-skipped providers not counted).",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary context metadata (application-level tags, request IDs, etc.).",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the routing run completed.",
    )

    @property
    def succeeded(self) -> bool:
        """``True`` when ``result`` is populated (routing produced a completion).

        Returns:
            Whether the routing run was successful.
        """
        return self.result is not None


@dataclass(init=False)
class ProviderUsage(DomainModel):
    """Quota usage record for a single provider on a single calendar day.

    Example:
        >>> usage = ProviderUsage(
        ...     provider="groq",
        ...     usage_date="2026-03-21",
        ...     success_count=42,
        ...     error_count=1,
        ...     is_exhausted=False,
        ... )
    """

    provider: str = Field(description="Provider name.")
    usage_date: str = Field(
        description="Calendar date (ISO 8601, UTC) this record tracks.",
    )
    success_count: int = Field(
        default=0,
        ge=0,
        description="Number of successful completions today.",
    )
    error_count: int = Field(
        default=0,
        ge=0,
        description="Number of non-exhaustion errors today.",
    )
    is_exhausted: bool = Field(
        default=False,
        description="``True`` when the provider has been quota-exhausted for today.",
    )
    exhausted_until: datetime | None = Field(
        default=None,
        description=(
            "Exhaustion expiry.  The provider is skipped only while "
            "``now < exhausted_until``; ``None`` means not exhausted."
        ),
    )
