"""Relay conversion context, options, and media callbacks.

The engine is synchronous and side-effect free.  Everything the engine
may need that depends on the host (Claude default ``max_tokens``,
Gemini safety thresholds, media resolution, model capabilities) is
supplied here as typed callbacks instead of globals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeAlias, runtime_checkable

from quadkit.contracts.ai.exceptions import RelayError
from quadkit.contracts.ai.relay.types import RelayLoss
from quadkit.contracts.core.result import Result

__all__ = [
    "ClaudeOptions",
    "DefaultMaxTokensCallback",
    "GeminiOptions",
    "MediaResolverProtocol",
    "PreserveThinkingSuffixCallback",
    "RelayConversionContext",
    "RelayOptions",
    "SafetySettingCallback",
    "SupportsImageGenerationCallback",
]


@dataclass(frozen=True)
class ClaudeOptions:
    """Claude-specific conversion adaptations.

    Attributes:
        thinking_adapter_enabled: Whether the Claude thinking adapter is
            active.  ``False`` disables the adaptation entirely.
        thinking_budget_percentage: Percentage of ``max_tokens`` the
            thinking adapter reserves for thinking output.  ``0`` disables
            the budget calculation.
        minimum_max_tokens: Floor the adapter applies to ``max_tokens``.
            ``0`` disables the floor.
    """

    thinking_adapter_enabled: bool = False
    thinking_budget_percentage: int = 0
    minimum_max_tokens: int = 0


@dataclass(frozen=True)
class GeminiOptions:
    """Gemini-specific conversion adaptations.

    Attributes:
        thinking_adapter_enabled: Whether the Gemini thinking adapter is
            active.  ``False`` disables the adaptation entirely.
        thinking_budget: Token budget for Gemini ``thinkingBudget``.
            ``0`` disables the budget calculation.
        thought_signature_bypass: Whether the thought-signature bypass
            policy is enabled for models that require it.
    """

    thinking_adapter_enabled: bool = False
    thinking_budget: int = 0
    thought_signature_bypass: bool = False


@dataclass(frozen=True)
class RelayOptions:
    """Cross-protocol conversion options.

    Zero-value options disable adaptations and must not add fields to
    outgoing payloads.

    Attributes:
        claude: Claude thinking/max_tokens adaptations.
        gemini: Gemini thinking/signature adaptations.
        model_suffix_preserved: Whether provider model suffixes (e.g.
            ``:thinking``) are preserved verbatim.
        openrouter_dialects: Whether OpenRouter-compatible dialect flags
            are honored.  Only meaningful when the host enables them.
    """

    claude: ClaudeOptions = field(default_factory=ClaudeOptions)
    gemini: GeminiOptions = field(default_factory=GeminiOptions)
    model_suffix_preserved: bool = False
    openrouter_dialects: bool = False


DefaultMaxTokensCallback: TypeAlias = Callable[[str], int | None]
"""Return a default ``max_tokens`` for a model, or ``None``."""

SafetySettingCallback: TypeAlias = Callable[[str], str | None]
"""Return a Gemini safety threshold for a category, or ``None``."""

SupportsImageGenerationCallback: TypeAlias = Callable[[str], bool]
"""Whether a model supports Gemini image generation."""

PreserveThinkingSuffixCallback: TypeAlias = Callable[[str], bool]
"""Whether a model requires the thinking-suffix bypass policy."""


@runtime_checkable
class MediaResolverProtocol(Protocol):
    """Resolves URL media into wire-ready base64.

    The engine never performs network I/O.  When a source payload carries
    a URL the target protocol cannot consume directly, the engine calls
    the resolver supplied through :class:`RelayConversionContext`.  The
    gateway may pre-resolve media asynchronously before calling the
    engine.
    """

    def resolve(self, url: str) -> Result[tuple[str, str], RelayError]:
        """Resolve *url* into ``(media_type, base64_data)``.

        Args:
            url: The source URL that requires conversion.

        Returns:
            ``Ok((media_type, base64_data))`` on success, or
            ``Err(RelayError)`` when resolution fails.
        """
        ...


@dataclass(frozen=True)
class RelayConversionContext:
    """Host-supplied context for one conversion.

    Attributes:
        options: Cross-protocol adaptation options.
        default_max_tokens: Claude ``max_tokens`` fallback when the source
            omitted it.  ``None`` means no fallback exists.
        safety_setting: Gemini safety threshold lookup by category.
        supports_image_generation: Gemini image-generation capability
            lookup by model.
        preserve_thinking_suffix: Thinking-suffix bypass policy lookup.
        media_resolver: Resolver for URL media, or ``None``.
        upstream_model: Host model name substituted when the source
            payload carries no model (e.g. Gemini responses).  Empty
            string disables substitution.
        losses: Per-conversion loss records appended by mappers; copied
            into the ``RelayConvertResult`` by the engine.
        request_id: Caller-supplied request id stamped on losses and
            errors during conversion.  Empty string when not provided.
        channel_name: Name of the selected relay channel, used for
            channel-aware adaptation and audit.  Empty string when not
            provided.
    """

    options: RelayOptions = field(default_factory=RelayOptions)
    default_max_tokens: DefaultMaxTokensCallback | None = None
    safety_setting: SafetySettingCallback | None = None
    supports_image_generation: SupportsImageGenerationCallback | None = None
    preserve_thinking_suffix: PreserveThinkingSuffixCallback | None = None
    media_resolver: MediaResolverProtocol | None = None
    upstream_model: str = ""
    losses: list[RelayLoss] = field(default_factory=list)
    request_id: str = ""
    channel_name: str = ""
