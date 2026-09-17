"""Thinking/reasoning value types shared across AI packages.

These types are provider-agnostic.  Every LLM client that supports extended
thinking or chain-of-thought reasoning normalises its output into
:class:`ThinkingResult` and accepts configuration via :class:`ThinkingConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ThinkingConfig",
    "ThinkingResult",
]


@dataclass(frozen=True)
class ThinkingConfig:
    """Provider-agnostic thinking/reasoning configuration.

    Pass as ``LLMConfig.thinking`` to enable extended thinking on any
    supporting provider.  ``None`` means thinking is disabled.

    Attributes:
        suppress: When True, actively suppresses thinking tokens by injecting
            ``enable_thinking: false`` (and ``chat_template_kwargs.enable_thinking: false``)
            into the request payload. Use this for models that generate thinking
            by default (Qwen3, Gemma-4 via LM Studio / vLLM / SGLang) when you
            do not want the latency cost. Mutually exclusive with ``effort``,
            ``budget_tokens``, and ``level`` — if ``suppress`` is True the other
            fields are ignored.
        budget_tokens: Maximum tokens the model may spend on internal
            reasoning.  Applies to Anthropic (``budget_tokens``), Gemini 2.5
            (``thinkingBudget``), and AWS Bedrock Claude (``budget_tokens``).
            Ignored when ``level`` is set (Gemini 3 uses ``level`` instead).
        level: Gemini 3 thinking level.  One of ``"minimal"``, ``"low"``,
            ``"medium"``, ``"high"``.  When set, takes precedence over
            ``budget_tokens`` for Gemini 3 models.
        effort: OpenAI o-series reasoning effort.  One of ``"low"``,
            ``"medium"``, ``"high"``.  Mutually exclusive with ``budget_tokens``
            and ``level`` (different API surface).
    """

    suppress: bool = False
    budget_tokens: int = 10_000
    level: str | None = None
    effort: str | None = None


@dataclass(frozen=True)
class ThinkingResult:
    """Normalised thinking/reasoning output — consistent shape regardless of provider.

    Attributes:
        content: The full thinking/reasoning text produced by the model.
        signature: Anthropic-specific encrypted signature required to
            re-inject thinking blocks into subsequent assistant turns during
            multi-turn tool-use conversations.  ``None`` for all other
            providers.
        tokens: Number of tokens consumed by internal reasoning.  Populated
            from Gemini ``thoughtsTokenCount`` and OpenAI
            ``completion_tokens_details.reasoning_tokens``.  ``None`` when
            the provider does not report this value.
    """

    content: str
    signature: str | None = None
    tokens: int | None = None
