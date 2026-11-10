"""Gateway contracts for the relay engine.

Defines the channel configuration, gateway request/result value types,
gateway error, and the gateway service protocol implemented by the
``the optional provider`` extension package.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from quadkit.contracts.ai.relay.transport import RelayWireEvent
from quadkit.contracts.ai.relay.types import ConversionQuality, JsonValue, RelayFormat
from quadkit.contracts.core.result import Result


@dataclass(frozen=True, slots=True)
class RelayChannel:
    """Configuration of one upstream endpoint a gateway can route to.

    ``group`` is the routing scope the channel serves, and ``groups`` holds
    any *additional* scopes a channel is shared with — one physical channel
    often serves several. A request is eligible only for channels that list
    its group (see :meth:`serves_group`); the default ``"default"`` keeps
    every channel that never mentions groups serving every request that
    never mentions groups, so existing configurations select exactly as
    before. Beyond that, scope is exact: no group name is magic. A
    channel that genuinely serves everyone says so with ``public=True``
    rather than by claiming a group whose name happens to mean "all" —
    a silent wildcard is exactly the kind of routing behaviour that is
    impossible to reason about after the fact.

    ``models`` may be empty, which means **catch-all**: the channel serves
    any model it is asked for. That is how new-api represents aggregators and
    providers whose catalogue is not enumerable (undeclared media models);
    selection prefers channels that name the requested model and only falls
    back to catch-all ones when none does, so declaring a catalogue never
    makes a channel less reachable.

    ``cost_multiplier`` is the channel's price relative to list price, used
    only by ``routing_policy="cheapest"``. ``None`` means list price (1.0),
    which is what a host that does not track cost leaves it at — and such a
    host keeps the default ``"priority"`` policy, so cost never enters
    selection unless it is both declared and asked for.

    ``upstream_base_url`` may be empty, which means *this channel is not
    dialled by the gateway's HTTP transport*: an offline or host-local
    adaptor answers it, and the host resolves (or does not need) a URL.
    Selection never reads the field. A deployment that does dial through
    the gateway loader still has to supply one — that check belongs to the
    loader and to the transport that would otherwise build a garbage URL,
    not to a routing model that must also describe adaptor-backed rows.
    """

    name: str
    upstream_base_url: str
    target_format: RelayFormat
    models: tuple[str, ...]
    capabilities: frozenset[str] = frozenset()
    endpoint_kinds: frozenset[str] = frozenset()
    priority: int = 100
    weight: int = 100
    enabled: bool = True
    timeout_seconds: float = 60.0
    model_map: Mapping[str, str] = field(default_factory=dict)
    group: str = "default"
    groups: frozenset[str] = frozenset()
    public: bool = False
    cost_multiplier: float | None = None

    def __post_init__(self) -> None:
        """Validate the channel configuration."""
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.group:
            raise ValueError("group must not be empty")
        if self.cost_multiplier is not None and self.cost_multiplier <= 0:
            raise ValueError("cost_multiplier must be positive when set")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.weight < 0:
            raise ValueError("weight must not be negative")
        # A catch-all channel has no catalogue to intersect with, so its map
        # *is* the alias table: any key is addressable.
        unknown = set(self.model_map) - set(self.models) if self.models else set()
        if unknown:
            raise ValueError(
                f"model_map keys must be listed in models; unknown: {sorted(unknown)}"
            )

    def serves_group(self, group: str) -> bool:
        """Whether this channel is in scope for *group*.

        Args:
            group: The routing scope the caller belongs to.

        Returns:
            ``True`` when the channel is public, lists the group in
            ``group`` or ``groups``. Membership is otherwise exact — an
            empty request group never matches, and no group is implicit.
        """
        return self.public or group == self.group or group in self.groups

    def resolve_model(self, alias: str) -> str:
        """Resolve the upstream model name for *alias*.

        The mapping wins when it carries *alias*; otherwise the alias is
        used as its own upstream name. This is what makes a catch-all
        channel's alias table work without a declared catalogue.

        Args:
            alias: The client-visible model alias.

        Returns:
            The model name sent to the channel's upstream.
        """
        return self.model_map.get(alias, alias)


@dataclass(frozen=True, slots=True)
class RelayGatewayRequest:
    """A request accepted by the relay gateway for dispatch.

    The ``channel`` field is a preferred-channel hint and audit
    snapshot: the service always re-selects the channel through the
    registry and never routes on this snapshot alone.
    """

    request_id: str
    tenant_id: str
    source: RelayFormat
    model: str
    stream: bool
    payload: Mapping[str, JsonValue]
    headers: Mapping[str, str]
    channel: RelayChannel | None = None
    group: str = "default"


@dataclass(frozen=True, slots=True)
class RelayGatewayResult:
    """The outcome of a relay gateway handle call."""

    status_code: int
    headers: Mapping[str, str]
    payload: Mapping[str, JsonValue] | None = None
    stream: AsyncIterator[RelayWireEvent] | None = None
    metadata: RelayGatewayMetadata | None = None


@dataclass(frozen=True, slots=True)
class RelayGatewayMetadata:
    """Conversion bookkeeping attached to a gateway result."""

    converter_id: str
    source: RelayFormat
    target: RelayFormat
    quality: ConversionQuality
    loss_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class RelayGatewayErrorCode(StrEnum):
    """Stable machine-readable codes carried by :class:`RelayGatewayError`.

    Existing callers may construct ``RelayGatewayError`` with the plain
    string value (``"INVALID_REQUEST"``); the members compare equal to
    those strings.

    Attributes:
        CHANNEL_DISABLED: No enabled channel exists.
        TARGET_FORMAT_UNSUPPORTED: No channel transforms the source format.
        CAPABILITY_UNAVAILABLE: No channel satisfies the capability filters.
        MODEL_NOT_FOUND: No channel serves the requested model.
        INVALID_REQUEST: The request payload is malformed.
        UNSUPPORTED_FORMAT: Unknown wire format.
        ENCODE_FAILED: Outbound payload serialization failed.
        DECODE_FAILED: Inbound payload deserialization failed.
        AUTH_DENIED: The caller is not authorized to invoke the model.
        PERMISSION_DENIED: The operator is not authorized for the
            requested control surface.
        UPSTREAM_ERROR: The upstream responded with a non-2xx status.
        UPSTREAM_TIMEOUT: The upstream request timed out.
        UPSTREAM_CANCELLED: The upstream request was cancelled.
        UPSTREAM_FAILED: Generic upstream transport failure.
        UPSTREAM_MALFORMED: A 2xx upstream body was malformed.
        CONVERSION_FAILED: Request/response conversion failed.
        STREAM_ERROR: A streaming session failed.
        QUOTA_EXCEEDED: Billing denied admission to the request.
        BILLING_FAILED: The billing pipeline failed unexpectedly.
        DEPENDENCY_UNAVAILABLE: An optional runtime dependency was not
            registered (e.g. the converter registry).
    """

    CHANNEL_DISABLED = "CHANNEL_DISABLED"
    TARGET_FORMAT_UNSUPPORTED = "TARGET_FORMAT_UNSUPPORTED"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    ENCODE_FAILED = "ENCODE_FAILED"
    DECODE_FAILED = "DECODE_FAILED"
    AUTH_DENIED = "AUTH_DENIED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_CANCELLED = "UPSTREAM_CANCELLED"
    UPSTREAM_FAILED = "UPSTREAM_FAILED"
    UPSTREAM_MALFORMED = "UPSTREAM_MALFORMED"
    CONVERSION_FAILED = "CONVERSION_FAILED"
    STREAM_ERROR = "STREAM_ERROR"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    BILLING_FAILED = "BILLING_FAILED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RelayGatewayError(Exception):
    """A domain error returned (or raised) by the relay gateway."""

    code: str
    message: str
    status_code: int
    request_id: str
    retryable: bool = False


@runtime_checkable
class RelayRuntimeEnableProtocol(Protocol):
    """Runtime eligibility overrides for routing targets.

    The relay gateway's ``RelayChannelRegistry`` implements this over its
    static channel table, and it is the surface the failover tracker and the
    operator controls both write. It is a protocol rather than a concrete
    dependency so a host that selects channels from its own store (a
    database, a control plane) can hand the tracker *its* eligibility
    surface instead of being forced onto the gateway's static table.

    Implementations must treat "not listed" as eligible: only an explicit
    override takes a target out of service.
    """

    def set_runtime_enabled(self, channel: str, enabled: bool) -> None:
        """Take *channel* out of service, or restore it.

        Args:
            channel: The routing target's identity (a channel name).
            enabled: ``False`` drains the target; ``True`` restores it.
        """
        ...

    def runtime_enabled(self) -> Mapping[str, bool]:
        """Return the non-default overrides.

        Returns:
            A mapping of target identity to ``False`` for drained targets.
        """
        ...


@runtime_checkable
class RelayGatewayProtocol(Protocol):
    """Service protocol implemented by the relay gateway."""

    async def handle(
        self, request: RelayGatewayRequest
    ) -> Result[RelayGatewayResult, RelayGatewayError]: ...
