"""Relay usage, reservation, and billing contracts.

Shared accounting protocols and value types for relay gateway billing:
usage scopes, reservations, settlement records, charge breakdowns, and
the store/estimator/billing protocols implemented by the governance
package.  All monetary fields use non-negative ``Decimal`` values; the
contracts never carry raw request payloads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from quadkit.contracts.ai.relay import (
    JsonValue,
    RelayConvertResult,
    RelayRequestPayload,
    RelayUsage,
)
from quadkit.contracts.core.result import Result

__all__ = [
    "RelayBillingError",
    "RelayBillingProtocol",
    "RelayChargeBreakdown",
    "RelayPriceEstimatorProtocol",
    "RelayUsageRecord",
    "RelayUsageReservation",
    "RelayUsageScope",
    "RelayUsageStoreProtocol",
    "billing_store_unavailable",
    "charge_overflow",
    "duplicate_settlement",
    "invalid_usage",
    "quota_exhausted",
    "reservation_expired",
    "unknown_price",
]

_RELAY_USAGE_TOKEN_FIELDS = (
    "prompt_tokens",
    "completion_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "reasoning_tokens",
    "audio_input_tokens",
    "audio_output_tokens",
    "image_tokens",
    "input_tokens",
    "output_tokens",
)


@dataclass(frozen=True, slots=True)
class RelayUsageScope:
    """Accounting scope for one relay request.

    Attributes:
        tenant_id: Tenant the charge is attributed to (required).
        account_id: Account the charge is attributed to, when applicable.
        user_id: User the charge is attributed to, when applicable.
        model: Model alias used for the request.
        provider: Provider name for the request.
        channel: Channel name for the request.
    """

    tenant_id: str
    account_id: str | None = None
    user_id: str | None = None
    model: str = ""
    provider: str = ""
    channel: str = ""

    def __post_init__(self) -> None:
        """Reject scopes without a tenant."""
        if not self.tenant_id:
            raise ValueError("tenant_id must be non-empty")


@dataclass(frozen=True, slots=True)
class RelayUsageRecord:
    """The settled accounting record for one request attempt.

    Attributes:
        request_id: Gateway request identifier.
        attempt_id: Attempt key; ``(request_id, attempt_id)`` is unique.
        scope: Accounting scope of the request.
        usage: Actual normalized usage that was billed.
        charge: Final charge in ``currency`` units (never negative).
        currency: ISO currency code of the charge.
        status: Terminal lifecycle status of the attempt.
        converter_id: Converter that produced the usage, when known.
        loss_codes: Conversion loss codes recorded alongside usage.
    """

    request_id: str
    attempt_id: str
    scope: RelayUsageScope
    usage: RelayUsage
    charge: Decimal
    currency: str
    status: Literal["completed", "failed", "cancelled", "truncated"]
    converter_id: str | None = None
    loss_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject invalid identities, usage, charges, and statuses."""
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if not self.attempt_id:
            raise ValueError("attempt_id must be non-empty")
        for field_name in _RELAY_USAGE_TOKEN_FIELDS:
            if getattr(self.usage, field_name) < 0:
                raise ValueError(f"usage.{field_name} must be non-negative")
        if (
            self.usage.total_tokens_override is not None
            and self.usage.total_tokens_override < 0
        ):
            raise ValueError("usage.total_tokens_override must be non-negative")
        if self.charge < 0:
            raise ValueError("charge must be non-negative")
        if not self.currency:
            raise ValueError("currency must be non-empty")
        if self.status not in ("completed", "failed", "cancelled", "truncated"):
            raise ValueError(f"unknown billing status: {self.status}")


@dataclass(frozen=True, slots=True)
class RelayUsageReservation:
    """Capacity reserved for a request before upstream admission.

    Attributes:
        reservation_id: Unique reservation identifier.
        request_id: Gateway request identifier the reservation belongs to.
        estimated_tokens: Prompt estimate used for admission only; never
            billed as final usage.
        estimated_charge: Maximum charge covered by the reservation.
        expires_at: Expiry instant (timezone-aware); a non-positive TTL
            is rejected at construction.
    """

    reservation_id: str
    request_id: str
    estimated_tokens: int
    estimated_charge: Decimal
    expires_at: datetime

    def __post_init__(self) -> None:
        """Reject invalid identities, estimates, and expiries."""
        if not self.reservation_id:
            raise ValueError("reservation_id must be non-empty")
        if not self.request_id:
            raise ValueError("request_id must be non-empty")
        if self.estimated_tokens < 0:
            raise ValueError("estimated_tokens must be non-negative")
        if self.estimated_charge < 0:
            raise ValueError("estimated_charge must be non-negative")
        if self.expires_at <= datetime.now(UTC):
            raise ValueError("reservation TTL must be positive")


@dataclass(frozen=True, slots=True)
class RelayChargeBreakdown:
    """Per-dimension charge breakdown of one estimate or settlement.

    Attributes:
        prompt: Charge for input tokens.
        cached_prompt: Charge for cached input tokens.
        completion: Charge for output tokens.
        reasoning: Charge for reasoning tokens.
        audio_input: Charge for audio input tokens.
        audio_output: Charge for audio output tokens.
        image: Charge for image input tokens.
        total: Total charge; must equal the configured sum after rounding.
    """

    prompt: Decimal
    cached_prompt: Decimal
    completion: Decimal
    reasoning: Decimal
    audio_input: Decimal
    audio_output: Decimal
    image: Decimal
    total: Decimal

    def __post_init__(self) -> None:
        """Reject negative prices in any dimension."""
        for field_name in (
            "prompt",
            "cached_prompt",
            "completion",
            "reasoning",
            "audio_input",
            "audio_output",
            "image",
            "total",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"breakdown.{field_name} must be non-negative")


@dataclass(frozen=True, slots=True)
class RelayBillingError:
    """A domain error returned from billing operations.

    Attributes:
        code: Machine-readable error code (e.g. ``unknown_price``).
        message: Public, redaction-safe error message.  Never contains
            raw request payloads, prompts, or credentials.
        request_id: Request identifier the error applies to, when known.
        tenant_id: Tenant the error applies to, when known.
    """

    code: str
    message: str
    request_id: str | None = None
    tenant_id: str | None = None


@runtime_checkable
class RelayUsageStoreProtocol(Protocol):
    """Persistence boundary for reservations and settled usage records."""

    async def save_reservation(self, reservation: RelayUsageReservation) -> None:
        """Persist a reservation atomically."""

    async def settle_once(self, record: RelayUsageRecord) -> RelayUsageRecord:
        """Settle a record exactly once, returning the stored record."""

    async def release(self, reservation_id: str) -> None:
        """Release a reservation, marking it as released."""

    async def query(
        self, filters: Mapping[str, JsonValue]
    ) -> Sequence[RelayUsageRecord]:
        """Query settled records by scope filters."""


@runtime_checkable
class RelayPriceEstimatorProtocol(Protocol):
    """Computes charges from normalized usage and configured prices.

    Pricing failures (unknown model, malformed price expressions,
    overflow) are returned as ``Err(RelayBillingError)`` — estimators
    never clamp silently.
    """

    def estimate_charge(
        self,
        model: str,
        usage: RelayUsage,
        *,
        provider: str = "",
        channel: str = "",
    ) -> Result[RelayChargeBreakdown, RelayBillingError]:
        """Return the charge breakdown for *usage* on *model*."""


@runtime_checkable
class RelayBillingProtocol(Protocol):
    """Billing lifecycle for one relay request.

    Callers invoke ``pre_consume`` after channel selection and before
    upstream I/O, then ``settle`` on completion, stream finalization, or
    failure, or ``release`` when the request never reached upstream.
    """

    async def pre_consume(
        self,
        request_id: str,
        scope: RelayUsageScope,
        payload: RelayRequestPayload,
    ) -> Result[RelayUsageReservation, RelayBillingError]:
        """Reserve capacity for a request before upstream admission."""

    async def settle(
        self,
        reservation: RelayUsageReservation,
        result: RelayConvertResult[RelayRequestPayload],
        *,
        status: Literal["completed", "failed", "cancelled", "truncated"],
    ) -> Result[RelayUsageRecord, RelayBillingError]:
        """Settle actual usage for a request attempt exactly once."""

    async def release(self, reservation: RelayUsageReservation) -> None:
        """Release a reservation when the request never reached upstream."""


def unknown_price(
    *,
    message: str = "unknown model price",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return an ``unknown_price`` billing error."""
    return RelayBillingError(
        code="unknown_price",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def quota_exhausted(
    *,
    message: str = "quota exhausted",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return a ``quota_exhausted`` billing error."""
    return RelayBillingError(
        code="quota_exhausted",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def reservation_expired(
    *,
    message: str = "reservation expired",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return a ``reservation_expired`` billing error."""
    return RelayBillingError(
        code="reservation_expired",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def duplicate_settlement(
    *,
    message: str = "duplicate settlement",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return a ``duplicate_settlement`` billing error."""
    return RelayBillingError(
        code="duplicate_settlement",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def invalid_usage(
    *,
    message: str = "invalid usage",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return an ``invalid_usage`` billing error."""
    return RelayBillingError(
        code="invalid_usage",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def billing_store_unavailable(
    *,
    message: str = "billing store unavailable",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return a ``billing_store_unavailable`` billing error."""
    return RelayBillingError(
        code="billing_store_unavailable",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )


def charge_overflow(
    *,
    message: str = "charge overflow",
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> RelayBillingError:
    """Return a ``charge_overflow`` billing error."""
    return RelayBillingError(
        code="charge_overflow",
        message=message,
        request_id=request_id,
        tenant_id=tenant_id,
    )
