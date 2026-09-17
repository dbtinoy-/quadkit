"""Relay operational read and control contracts.

Defines the health, capability, metric, report, and policy-control value
types and service protocols that the gateway and governance admin
surfaces consume.  Value types are immutable, redaction-safe, and reject
nonsense inputs at construction time; the service protocols are the only
cross-package boundary for operational data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from quadkit.contracts.ai.relay.types import ConversionQuality, RelayFormat

__all__ = [
    "RelayActiveStream",
    "RelayChannelHealth",
    "RelayOperationsControlProtocol",
    "RelayOperationsProtocol",
    "RelayPolicyChange",
    "RelayPolicySnapshot",
    "RelayPolicyStoreProtocol",
    "RelayRegistryDiagnostics",
    "RelayRouteMetrics",
    "TimeWindow",
]

_CHANNEL_HEALTH_STATUSES = frozenset({"healthy", "degraded", "unavailable", "failed"})
"""Stable channel health status values."""


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """A closed, forward time range for metric aggregation.

    Attributes:
        start: Inclusive window start (UTC).
        end: Inclusive window end (UTC), strictly after ``start``.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        """Reject empty and inverted windows."""
        if self.end <= self.start:
            raise ValueError("window end must be after window start")


@dataclass(frozen=True, slots=True)
class RelayActiveStream:
    """One in-flight upstream stream.

    Attributes:
        stream_id: Unique identifier of the stream session.
        channel: Name of the channel serving the stream.
        model: Outbound model alias of the stream.
        request_id: Gateway request identifier the stream belongs to.
        started_at: When the stream started (UTC).
    """

    stream_id: str
    channel: str
    model: str
    request_id: str
    started_at: datetime

    def __post_init__(self) -> None:
        """Reject empty identifiers."""
        if not self.stream_id:
            raise ValueError("stream_id must not be empty")
        if not self.channel:
            raise ValueError("channel must not be empty")
        if not self.request_id:
            raise ValueError("request_id must not be empty")


@dataclass(frozen=True, slots=True)
class RelayChannelHealth:
    """One gateway channel's operational health snapshot.

    Attributes:
        channel: Channel name.
        target: Target wire format the channel serves.
        status: Stable status value.
        model_count: Number of model aliases the channel serves.
        latency_ms_p50: Median request latency, or ``None`` when unknown.
        latency_ms_p95: P95 request latency, or ``None`` when unknown.
        failure_count: Upstream failures in the window.
        checked_at: When the snapshot was taken (UTC).
        detail_code: Machine-readable reason for degraded/failed status.
    """

    channel: str
    target: RelayFormat
    status: Literal["healthy", "degraded", "unavailable", "failed"]
    model_count: int
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    failure_count: int
    checked_at: datetime
    detail_code: str | None = None

    def __post_init__(self) -> None:
        """Validate the snapshot fields."""
        if not self.channel:
            raise ValueError("channel must not be empty")
        if self.status not in _CHANNEL_HEALTH_STATUSES:
            raise ValueError(f"unknown channel health status {self.status!r}")
        if self.model_count < 0:
            raise ValueError("model_count must not be negative")
        if self.failure_count < 0:
            raise ValueError("failure_count must not be negative")
        if self.latency_ms_p50 is not None and self.latency_ms_p50 < 0:
            raise ValueError("latency_ms_p50 must not be negative")
        if self.latency_ms_p95 is not None and self.latency_ms_p95 < 0:
            raise ValueError("latency_ms_p95 must not be negative")


@dataclass(frozen=True, slots=True)
class RelayRouteMetrics:
    """Aggregated conversion metrics for one directed route and window.

    Attributes:
        source: Source wire format.
        target: Target wire format.
        quality: Static conversion quality of the route.
        request_count: Completed requests on the route in the window.
        loss_counts: Conversion loss codes and their counts.
        unsupported_count: Requests dropped for unsupported features.
        stream_failure_count: Streams that failed on the route.
        converter_id: Route converter identifier, when known.
        window_start: Aggregation window start (UTC).
        window_end: Aggregation window end (UTC).
    """

    source: RelayFormat
    target: RelayFormat
    quality: ConversionQuality
    request_count: int
    loss_counts: Mapping[str, int]
    unsupported_count: int
    stream_failure_count: int
    converter_id: str | None
    window_start: datetime
    window_end: datetime

    def __post_init__(self) -> None:
        """Validate the aggregated counters."""
        if self.request_count < 0:
            raise ValueError("request_count must not be negative")
        if self.unsupported_count < 0:
            raise ValueError("unsupported_count must not be negative")
        if self.stream_failure_count < 0:
            raise ValueError("stream_failure_count must not be negative")
        if self.window_end <= self.window_start:
            raise ValueError("window end must be after window start")


@dataclass(frozen=True, slots=True)
class RelayRegistryDiagnostics:
    """Read-only registry state for operational diagnostics.

    Attributes:
        converter_id: Converter engine identifier.
        converter_version: Converter engine version string.
        mapper_ids: Registered mapper wire-format identifiers.
        supported_routes: Directed route pairs served by the engine.
        registration_errors: Errors observed at registration time.
    """

    converter_id: str
    converter_version: str
    mapper_ids: tuple[str, ...]
    supported_routes: tuple[tuple[RelayFormat, RelayFormat], ...]
    registration_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelayPolicySnapshot:
    """Current gateway routing policy.

    Attributes:
        enabled_channels: Channel name to enabled flag.
        allowed_model_options: Channel name to allowed option names.
        media_allowed_schemes: Media resolver URL schemes allowlist.
        media_allowed_hosts: Media resolver URL hosts allowlist.
        max_request_bytes: Maximum accepted request body size.
        max_stream_seconds: Maximum streaming duration.
    """

    enabled_channels: Mapping[str, bool]
    allowed_model_options: Mapping[str, frozenset[str]]
    media_allowed_schemes: frozenset[str]
    media_allowed_hosts: frozenset[str]
    max_request_bytes: int
    max_stream_seconds: float

    def __post_init__(self) -> None:
        """Validate the policy limits and allowlists."""
        if "*" in self.media_allowed_hosts:
            raise ValueError("media_allowed_hosts must not contain wildcards")
        if self.max_request_bytes < 0:
            raise ValueError("max_request_bytes must not be negative")
        if self.max_stream_seconds <= 0:
            raise ValueError("max_stream_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RelayPolicyChange:
    """A typed, partial policy mutation request.

    Only the fields explicitly set are changed; ``None`` means unchanged.
    """

    channel: str | None = None
    enabled: bool | None = None
    allowed_model_options: frozenset[str] | None = None
    media_allowed_schemes: frozenset[str] | None = None
    media_allowed_hosts: frozenset[str] | None = None
    max_request_bytes: int | None = None
    max_stream_seconds: float | None = None

    def __post_init__(self) -> None:
        """Validate the mutation payload."""
        if self.media_allowed_hosts is not None and "*" in self.media_allowed_hosts:
            raise ValueError("media_allowed_hosts must not contain wildcards")
        if self.max_request_bytes is not None and self.max_request_bytes < 0:
            raise ValueError("max_request_bytes must not be negative")
        if self.max_stream_seconds is not None and self.max_stream_seconds <= 0:
            raise ValueError("max_stream_seconds must be positive")


@runtime_checkable
class RelayPolicyStoreProtocol(Protocol):
    """Persistent backend for the runtime gateway routing policy.

    The store is the source of truth for ``RelayPolicySnapshot`` between
    control mutations: ``load`` returns the current snapshot and ``save``
    persists a full replacement atomically.
    """

    async def load(self) -> RelayPolicySnapshot:
        """Return the current policy snapshot.

        Returns:
            The current snapshot; a store that has never been written
            returns the initial snapshot it was constructed with.
        """
        ...

    async def save(self, snapshot: RelayPolicySnapshot) -> None:
        """Atomically replace the stored snapshot with *snapshot*.

        Args:
            snapshot: The full replacement snapshot. Partial updates are
                composed by the caller before saving.
        """
        ...


@runtime_checkable
class RelayOperationsProtocol(Protocol):
    """Read-only operational queries for admin surfaces."""

    async def channel_health(self) -> Sequence[RelayChannelHealth]:
        """Return a health snapshot per gateway channel.

        Returns:
            One snapshot per configured channel.  A dependency that is
            not registered yields an ``unavailable`` snapshot, never a
            fabricated healthy one.
        """
        ...

    async def route_metrics(
        self,
        window: TimeWindow,
    ) -> Sequence[RelayRouteMetrics]:
        """Return aggregated conversion metrics inside *window*.

        Args:
            window: Bounded aggregation window; unbounded windows are
                rejected by the caller.

        Returns:
            One aggregation per directed route that saw activity.
        """
        ...

    async def registry_diagnostics(self) -> RelayRegistryDiagnostics:
        """Return converter and mapper registry state.

        Returns:
            Engine identifier, version, mapper ids, and supported route
            pairs.  A missing converter is a failed dependency and is
            reported by the caller as such.
        """
        ...

    async def policy_snapshot(self) -> RelayPolicySnapshot:
        """Return the current routing policy.

        Returns:
            The current enabled-channel, option, media, and limit
            settings.
        """
        ...

    async def active_streams(self) -> Sequence[RelayActiveStream]:
        """Return the currently in-flight upstream streams.

        Returns:
            One row per active stream, oldest first; an empty sequence
            when no stream is in flight.
        """
        ...


@runtime_checkable
class RelayOperationsControlProtocol(Protocol):
    """Permissioned runtime control mutations."""

    async def set_channel_state(
        self,
        channel: str,
        enabled: bool,
        actor_id: str,
    ) -> None:
        """Enable or drain *channel* for new requests.

        Args:
            channel: Channel name; unknown names are rejected.
            enabled: ``False`` drains the channel for new requests while
                existing streams finish.
            actor_id: Operator identity recorded in the audit event.

        Raises:
            ValueError: The channel is unknown.
        """
        ...

    async def update_policy(
        self,
        change: RelayPolicyChange,
        actor_id: str,
    ) -> None:
        """Apply a typed policy change.

        Args:
            change: Partial policy mutation; only set fields change.
            actor_id: Operator identity recorded in the audit event.

        Raises:
            ValueError: The change references unknown channels or options.
        """
        ...

    async def policy_snapshot(self, actor_id: str) -> RelayPolicySnapshot:
        """Return the current routing policy for *actor_id*.

        Args:
            actor_id: Operator identity; ``relay.read`` permission is
                required.

        Returns:
            The current enabled-channel, option, media, and limit
            settings.

        Raises:
            RelayGatewayError: With ``PERMISSION_DENIED`` when the actor
                lacks ``relay.read``.
        """
        ...

    async def force_cancel_stream(
        self,
        stream_id: str,
        actor_id: str,
    ) -> None:
        """Force-cancel an in-flight upstream stream.

        Args:
            stream_id: Identifier of the stream to cancel. Unknown
                streams are rejected.
            actor_id: Operator identity recorded in the audit event;
                ``relay.stream_control`` permission is required.

        Raises:
            ValueError: The stream identifier is unknown.
            RelayGatewayError: With ``PERMISSION_DENIED`` when the actor
                lacks ``relay.stream_control``.
        """
        ...
