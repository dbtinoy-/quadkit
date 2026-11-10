"""Provider contracts: registry/selection protocols, and the vendor descriptor.

The first half of this module is runtime — which provider answers a model request,
what happens when one fails. The second half is data — the descriptor that says
what a vendor *is*, which both a gateway (for routing) and a fixture pack (for
evidence) are projected from.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

from quadkit.contracts.ai.types import ModelCapability

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import LLMClientProtocol


class SelectionStrategy(StrEnum):
    """Strategy for selecting which model/provider to use.

    Attributes:
        COST_OPTIMAL: Choose cheapest option that meets requirements
        LATENCY_OPTIMAL: Choose fastest provider
        CAPABILITY_MATCH: Choose first model supporting all required capabilities
        ROUND_ROBIN: Rotate through healthy providers
        PREFERRED: Try preferred provider, fallback to others
    """

    COST_OPTIMAL = "cost_optimal"
    LATENCY_OPTIMAL = "latency_optimal"
    CAPABILITY_MATCH = "capability_match"
    ROUND_ROBIN = "round_robin"
    PREFERRED = "preferred"


@dataclass(frozen=True)
class ModelInfo:
    """Information about an available LLM model.

    Attributes:
        model_id: Unique model identifier (e.g., "gpt-4o")
        provider: Provider name (e.g., "openai")
        display_name: Human-readable name
        capabilities: Set of capabilities this model has
        context_window: Input context window size in tokens
        max_output_tokens: Maximum output tokens this model can generate
        input_cost_per_million: Cost per million input tokens (USD)
        output_cost_per_million: Cost per million output tokens (USD)
        is_available: Whether model is currently available
        metadata: Additional provider-specific metadata
    """

    model_id: str
    provider: str
    display_name: str
    capabilities: frozenset[ModelCapability]
    context_window: int
    max_output_tokens: int
    input_cost_per_million: float
    output_cost_per_million: float
    is_available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    """Health status of a provider.

    Mutable dataclass tracking provider health metrics including
    latency, error rate, and availability status.

    Attributes:
        provider: Provider name
        is_healthy: Whether provider is considered healthy
        latency_ms: Average response latency in milliseconds
        error_rate: Error rate as a fraction (0-1)
        last_check: When health was last checked
        details: Additional health detail information
    """

    provider: str
    is_healthy: bool
    latency_ms: float
    error_rate: float
    last_check: datetime
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ProviderRegistryProtocol(Protocol):
    """Protocol for registering and discovering LLM providers.

    Maintains a registry of supported providers and their models,
    with health tracking and capability-based filtering.
    """

    async def register_provider(
        self, name: str, client: LLMClientProtocol, models: list[ModelInfo]
    ) -> None:
        """Register a new provider with its available models.

        Args:
            name: Provider name (e.g., "openai", "anthropic")
            client: The LLM client for this provider
            models: List of available models from this provider
        """
        ...

    async def get_client(self, provider: str) -> LLMClientProtocol | None:
        """Get the LLM client for a provider.

        Args:
            provider: Provider name

        Returns:
            The LLM client, or None if not registered
        """
        ...

    def list_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names
        """
        ...

    def list_models(
        self, capabilities: set[ModelCapability] | None = None
    ) -> list[ModelInfo]:
        """List all available models with optional capability filtering.

        Args:
            capabilities: If provided, return only models with all these capabilities

        Returns:
            List of model information
        """
        ...

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific model.

        Args:
            model_id: The model identifier

        Returns:
            Model information, or None if not found
        """
        ...


@runtime_checkable
class ModelSelectorProtocol(Protocol):
    """Protocol for selecting models based on criteria.

    Implements various selection strategies including cost optimization,
    latency optimization, and capability matching.
    """

    async def select(
        self,
        capabilities: set[ModelCapability],
        preferred_provider: str | None = None,
        max_cost_per_million: float | None = None,
        strategy: SelectionStrategy = SelectionStrategy.COST_OPTIMAL,
    ) -> ModelInfo | None:
        """Select a model based on the given criteria.

        Args:
            capabilities: Required capabilities for the model
            preferred_provider: Prefer this provider if possible
            max_cost_per_million: Maximum cost threshold (if relevant to strategy)
            strategy: Selection strategy to use

        Returns:
            Selected model info, or None if no suitable model found
        """
        ...


@runtime_checkable
class FallbackChainProtocol(Protocol):
    """Protocol for executing requests with provider fallback.

    Handles cascading requests across multiple providers with
    automatic fallback on failure.
    """

    async def execute(self, request: Any, providers: list[str]) -> Any:
        """Execute request with automatic fallback to other providers.

        Tries providers in order until one succeeds.

        Args:
            request: The request to execute
            providers: List of provider names to try in order

        Returns:
            The response from the first successful provider

        Raises:
            AllProvidersExhaustedError: If all providers failed
        """
        ...


# ── The provider descriptor ───────────────────────────────────────────────
#
# One description of a vendor, projected twice: the gateway reads it for routing
# (channel type, wire family, capabilities, path map) and a fixture pack reads it
# for evidence (operations, credential policy, source pins). The description is
# data — frozen, validated on construction, and free of HTTP, database and
# container imports — so the licence question attaches to a relay
# implementation rather than to a vendor's description.
#
# Scope, stated because PROV-2 names a wider one: the spec also proposes moving
# `OperationSpec`, `APIVersion` and `ContractEvidence` here *from the fixture
# kernel*. That is deliberately not done here. Those three are the kernel's own
# value types, 30 pack wheels import the kernel, and FX-5 pinned the fixture
# package's base distribution to `dependencies = []` on purpose. Moving them
# changes that edge rather than renaming a name, so it is PROV-2b and is written
# down in the spec with the trade-off. Nothing below is a second definition of an
# existing name: `OperationMap` is a routing row — gateway path ↔ vendor path plus
# a translation strategy — not a contract operation.
#
# Validation lives here rather than in a test for the same reason
# `BuildBlock.__post_init__` does: a descriptor that contradicts itself is a build
# that routes traffic nobody designed, and two live cases prove it — a vendor that
# declares API_KEY_HEADER without naming the header, and two vendors claiming one
# channel type (new-api's numbering already has three Azure types on one wire, so
# the alias field is load-bearing rather than decorative).


class WireFamily(StrEnum):
    """How much of a request has to be rewritten to talk to this vendor.

    The adaptor class is chosen from this, not from the vendor name, which is
    what makes "add a provider" a data change rather than a code change.
    """

    #: OpenAI-shaped; passthrough plus header/URL deltas.
    OPENAI_COMPAT = "openai_compat"
    #: Request *and* response translation.
    NATIVE = "native"
    #: Create → poll → fetch.
    TASK_ASYNC = "task_async"
    #: Multipart, audio or file bodies.
    BINARY = "binary"
    #: Embedding and rerank shapes.
    EMBED_RERANK = "embed_rerank"


class ProviderCapability(StrEnum):
    """What a vendor can do, as the console and the router both read it.

    Namespaced with the ``Provider`` prefix because this package already exports
    ``ModelCapability`` (a per-model property) from
    :mod:`quadkit.contracts.ai.types`, and two types called "capability" in one
    import list is how the wrong one gets used.
    """

    CHAT = "chat"
    STREAM = "stream"
    TOOLS = "tools"
    EMBEDDINGS = "embeddings"
    RERANK = "rerank"
    IMAGE = "image"
    VIDEO = "video"
    TTS = "tts"
    #: Responses compaction — a shape, not a modality.
    COMPACT = "compact"


class AuthMode(StrEnum):
    """How a credential travels to the vendor."""

    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    #: In the query string. Gemini puts the key there (`gemini.py:82` builds
    #: `...:generateContent?key=...`), so a descriptor that cannot say so cannot
    #: describe a real vendor.
    API_KEY_QUERY = "api_key_query"
    BASIC = "basic"
    NONE = "none"


class Vocabulary(StrEnum):
    """Which numbering scheme a descriptor's channel types belong to.

    new-api's integer space is what every existing channel row carries; the
    offline ids (66 stub, 69 authored) extend it. Naming the vocabulary means
    a future renumbering is a migration of descriptors rather than a hunt through
    ``pipeline.py``.
    """

    NEWAPI = "newapi"
    EXTENDED = "extended"


class Translation(StrEnum):
    """What has to happen between the gateway path and the vendor path."""

    PASSTHROUGH = "passthrough"
    ADAPTER = "adapter"
    TASK_POLL = "task_poll"
    MULTIPART = "multipart"


@dataclass(frozen=True, slots=True)
class AuthStyle:
    """A credential's transport, naming the header or the query parameter.

    Exactly one of the two names is legal, and only for the mode that uses it:
    `Authorization` on a bearer vendor is implied, and a stray second name beside
    it is exactly the quiet drift this type prevents.
    """

    mode: AuthMode
    header: str | None = None
    #: The query parameter the key travels in, for `API_KEY_QUERY` only.
    parameter: str | None = None
    #: The `Authorization` scheme prefix, for `BEARER` only. Defaults to
    #: ``Bearer``; fal sends ``Key`` (``providers/fal.py``), and a descriptor that
    #: cannot say so would have to lie about the vendor.
    scheme: str | None = None

    def __post_init__(self) -> None:
        if self.scheme is not None and self.mode is not AuthMode.BEARER:
            raise ValueError(f"{self.mode.value} auth must not name a scheme")
        if self.mode is AuthMode.API_KEY_HEADER:
            if self.parameter is not None:
                raise ValueError("api_key_header auth must not name a query parameter")
            if not (self.header or "").strip():
                raise ValueError(
                    "api_key_header auth must name the header it sends the key in"
                )
        elif self.mode is AuthMode.API_KEY_QUERY:
            if self.header is not None:
                raise ValueError("api_key_query auth must not name a header")
            if not (self.parameter or "").strip():
                raise ValueError(
                    "api_key_query auth must name the query parameter it sends"
                )
        elif self.header is not None or self.parameter is not None:
            # `Authorization` on a bearer vendor is implied; a stray second name
            # beside it is exactly the quiet drift this type prevents.
            raise ValueError(
                f"{self.mode.value} auth must not name a header or parameter"
            )


@dataclass(frozen=True, slots=True)
class AliasSpec:
    """An extra channel type that lands on the same vendor and wire.

    Azure's three ids and OpenRouter's second are the live cases: distinct rows
    with distinct keys that must resolve to one adaptor.
    """

    channel_type: int
    reason: str

    def __post_init__(self) -> None:
        if isinstance(self.channel_type, bool) or not isinstance(
            self.channel_type, int
        ):
            raise TypeError("alias channel_type must be an integer")
        if self.channel_type < 1:
            raise ValueError("alias channel_type must be positive")
        if not self.reason.strip():
            raise ValueError("an alias must say why it exists")


@dataclass(frozen=True, slots=True)
class OperationMap:
    """One operation: what the gateway accepts, and what the vendor expects."""

    operation_id: str
    gateway_method: str
    gateway_path: str
    upstream_method: str
    upstream_path: str
    translation: Translation = Translation.PASSTHROUGH
    #: Query parameters the upstream call must carry, as ``(name, value)`` pairs.
    #:
    #: Separate from ``upstream_path`` because that field forbids a query — a
    #: vendor that selects streaming through the URL rather than a JSON flag has
    #: to say so somewhere, and appending it to the path would make a field named
    #: ``path`` carry a query.
    #:
    #: Measured across all 30 packs: two operations need it, both the streaming
    #: variant of a Gemini-wire vendor, and both adaptors already send it
    #: (``?alt=sse``). Nothing in the tree reads it from the pack, which is why it
    #: survived the transcription to PROV-5 unnoticed.
    upstream_query: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id must not be empty")
        for name in ("gateway_method", "upstream_method"):
            value = getattr(self, name)
            if (
                value != value.upper()
                or not value.isalpha()
                or not 3 <= len(value) <= 12
            ):
                raise ValueError(
                    f"{name} must be an uppercase HTTP method, got {value!r}"
                )
        for name in ("gateway_path", "upstream_path"):
            value = getattr(self, name)
            if not value.startswith("/"):
                raise ValueError(f"{name} must be an absolute path, got {value!r}")
            if "?" in value or "#" in value:
                raise ValueError(f"{name} must not carry a query or fragment")
            if "//" in value or any(part in {".", ".."} for part in value.split("/")):
                raise ValueError(f"{name} contains an ambiguous segment")
        names = [name for name, _ in self.upstream_query]
        if len(set(names)) != len(names) or any(
            not name.strip() or not value.strip() for name, value in self.upstream_query
        ):
            raise ValueError(
                "upstream_query must be distinct non-empty name/value pairs"
            )


@dataclass(frozen=True, slots=True)
class FixtureRef:
    """The pack profile that answers this provider offline, when one does.

    A provider with no fixture profile is not an omission to hide: the descriptor
    carries the *reason* instead, because "we never wrote one" and "the vendor's
    terms forbid recording one" are different states for a reviewer.
    """

    profile_id: str
    profile_release: str

    def __post_init__(self) -> None:
        for name in ("profile_id", "profile_release"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class SourcePin:
    """One vendored artifact the descriptor's claims rest on."""

    path: str
    revision: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("a source pin must name the artifact it pins")
        if not self.revision.strip():
            raise ValueError(f"source pin {self.path!r} must name a revision")
        if self.sha256 is not None and len(self.sha256) != 64:
            raise ValueError(f"source pin {self.path!r} carries a malformed sha256")


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """A vendor, described once."""

    provider_id: str
    display_name: str
    channel_type: int
    wire: WireFamily
    #: The vendor's public endpoint, when it is a stable constant. ``None`` means
    #: the operator supplies one — measured: only three channel types have a
    #: default in the tree (``shared/provider_base_urls.py``) against twenty-five
    #: that are dispatched, so a required field would be a fabrication for most.
    base_url: str | None
    auth: AuthStyle
    capabilities: frozenset[ProviderCapability]
    #: The ``AdaptorRegistry`` key this provider dispatches to, when the wire
    #: family's default would be wrong.
    #:
    #: Most ``OPENAI_COMPAT`` vendors share one adaptor, so "openai" is derived
    #: from the family and a field per vendor would repeat it twenty-five times.
    #: The six that do not share it say so here: five name their own adaptor
    #: (alibaba, deepseek, minimax, responses, authored) and one names a
    #: differently-keyed one (the offline stub -> stub).
    #:
    #: This is what makes "add a descriptor, change no Python" true of *dispatch*
    #: too: before it, a vendor with its own adaptor was a Python edit in
    #: ``modules/relay/channel_types.py``, which is the module the derivation
    #: lives in rather than a descriptor.
    adaptor_name: str | None = None
    #: The API versions the *channel* accepts, for the vendors whose version is
    #: not a segment of every operation's path.
    #:
    #: Measured across all 30 packs: 27 operations declare a version that already
    #: sits in the path (``/v1/...``, ``/v1beta/...``), so ``upstream_path``
    #: carries it and this stays empty. Anthropic is the sole exception — its
    #: version travels in the ``anthropic-version`` header and *selects the
    #: credential transport*, so a descriptor that cannot name it cannot describe
    #: the vendor. The values match the set the adaptor itself validates against.
    api_versions: tuple[str, ...] = ()
    vocabulary: Vocabulary = Vocabulary.NEWAPI
    aliases: tuple[AliasSpec, ...] = ()
    operations: tuple[OperationMap, ...] = ()
    #: Every profile that answers this vendor offline. Plural because the tree
    #: ships 30 packs against 25 channel types: Anthropic has three profiles
    #: (messages-2023, messages-2026, stream-2026) and one reference would drop
    #: two of them silently.
    fixtures: tuple[FixtureRef, ...] = ()
    fixtures_absent_reason: str | None = None
    pricing_ns: str = "default"
    sources: tuple[SourcePin, ...] = ()

    def __post_init__(self) -> None:
        for name in ("provider_id", "display_name", "pricing_ns"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if isinstance(self.channel_type, bool) or not isinstance(
            self.channel_type, int
        ):
            raise TypeError("channel_type must be an integer")
        if self.channel_type < 1:
            raise ValueError("channel_type must be positive")
        if self.base_url is not None and not self.base_url.startswith(
            ("https://", "http://")
        ):
            raise ValueError(
                f"base_url {self.base_url!r} must be absolute http(s); a relative one "
                "would be resolved against the gateway by accident"
            )
        if self.api_versions and (
            not isinstance(self.api_versions, tuple)
            or any(not isinstance(v, str) or not v.strip() for v in self.api_versions)
            or len(set(self.api_versions)) != len(self.api_versions)
        ):
            raise ValueError("api_versions must be distinct non-empty version strings")
        if not isinstance(self.capabilities, frozenset):
            # A mutable set here would be shared state across every reader.
            object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        if not self.capabilities:
            raise ValueError("a provider with no capability cannot be routed to")
        if (
            ProviderCapability.STREAM in self.capabilities
            and ProviderCapability.CHAT not in (self.capabilities)
        ):
            raise ValueError(
                "STREAM without CHAT describes a vendor nothing can ask to stream"
            )

        seen = {self.channel_type}
        for alias in self.aliases:
            if alias.channel_type in seen:
                raise ValueError(f"channel type {alias.channel_type} is claimed twice")
            seen.add(alias.channel_type)

        operation_ids = [operation.operation_id for operation in self.operations]
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError("operation ids must be unique within a provider")

        # Exactly one of the two: a fixture reference, or the reason there is none.
        profile_ids = [fixture.profile_id for fixture in self.fixtures]
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("a provider may not reference one fixture profile twice")
        has_ref = bool(self.fixtures)
        has_reason = bool((self.fixtures_absent_reason or "").strip())
        if has_ref and has_reason:
            raise ValueError(
                "a provider cannot both ship fixtures and explain their absence"
            )
        if not has_ref and not has_reason:
            raise ValueError(
                "a provider must ship fixtures or say why it has none — silence is the "
                "state nobody can act on"
            )

    @property
    def channel_types(self) -> tuple[int, ...]:
        """Every channel type that resolves to this provider, primary first."""
        return (self.channel_type, *(alias.channel_type for alias in self.aliases))

    @property
    def requires_operator_base_url(self) -> bool:
        """Whether the operator has to supply the upstream URL for this vendor."""
        return self.base_url is None

    @property
    def fixture_profile_ids(self) -> tuple[str, ...]:
        """Every fixture profile that answers this vendor offline."""
        return tuple(fixture.profile_id for fixture in self.fixtures)

    def operation(self, operation_id: str) -> OperationMap | None:
        """The operation called ``operation_id``, or ``None``."""
        for operation in self.operations:
            if operation.operation_id == operation_id:
                return operation
        return None


def routing_table(
    descriptors: Iterable[ProviderDescriptor],
) -> dict[int, ProviderDescriptor]:
    """Index descriptors by channel type, refusals included.

    This is the map a gateway builds at boot from the installed descriptors, and
    it is what replaces the 22-entry ``int → name`` dictionary that lives inside
    ``pipeline.py`` today. Two descriptors claiming one channel type is a build
    error rather than a last-one-wins silence — the failure mode PROV-1 removed
    for unknown types would otherwise come back as "whichever won the import".

    Args:
        descriptors: The installed descriptors.

    Returns:
        Channel type → descriptor, aliases included.

    Raises:
        ValueError: Two descriptors claim the same channel type.
    """
    table: dict[int, ProviderDescriptor] = {}
    for descriptor in descriptors:
        for channel_type in descriptor.channel_types:
            existing = table.get(channel_type)
            if existing is not None and existing.provider_id != descriptor.provider_id:
                raise ValueError(
                    f"channel type {channel_type} is claimed by both "
                    f"{existing.provider_id!r} and {descriptor.provider_id!r}"
                )
            table[channel_type] = descriptor
    return table


def ensure_unique_provider_ids(descriptors: Iterable[ProviderDescriptor]) -> None:
    """Refuse two descriptors for one provider id.

    Separate from :func:`routing_table` because the two failures have different
    fixes: a duplicate channel type is a renumbering, a duplicate provider id is
    a descriptor that should have been an alias.

    Args:
        descriptors: The installed descriptors.

    Raises:
        ValueError: One provider id appears twice.
    """
    seen: set[str] = set()
    for descriptor in descriptors:
        if descriptor.provider_id in seen:
            raise ValueError(f"provider {descriptor.provider_id!r} is described twice")
        seen.add(descriptor.provider_id)


__all__ = [
    "AliasSpec",
    "AuthMode",
    "AuthStyle",
    "FallbackChainProtocol",
    "FixtureRef",
    "ModelInfo",
    "ModelSelectorProtocol",
    "OperationMap",
    "ProviderCapability",
    "ProviderDescriptor",
    "ProviderHealth",
    "ProviderRegistryProtocol",
    "SelectionStrategy",
    "SourcePin",
    "Translation",
    "Vocabulary",
    "WireFamily",
    "ensure_unique_provider_ids",
    "routing_table",
]
