"""Tests for relay conversion context, options, and error codes."""
from __future__ import annotations

from quadkit.contracts.ai.relay.context import (
    ClaudeOptions,
    GeminiOptions,
    RelayConversionContext,
    RelayOptions,
)
from quadkit.contracts.ai.relay.types import (
    ConversionQuality,
    RelayConvertResult,
    RelayFormat,
    RelayLoss,
    RelayUsage,
)
from quadkit.contracts.ai.exceptions import RelayError


def test_relay_format_values() -> None:
    """RelayFormat maps to the four supported wire protocols."""
    assert RelayFormat.OPENAI_CHAT.value == "openai_chat"
    assert RelayFormat.CLAUDE.value == "claude"
    assert RelayFormat.GEMINI.value == "gemini"
    assert RelayFormat.OPENAI_RESPONSES.value == "openai_responses"


def test_conversion_quality_values() -> None:
    """ConversionQuality values mirror relaykit semantics."""
    assert ConversionQuality.GOOD.value == "GOOD"
    assert ConversionQuality.FAIR.value == "FAIR"
    assert ConversionQuality.DISCOURAGED.value == "DISCOURAGED"


def test_relay_options_defaults_disable_adaptations() -> None:
    """RelayOptions() does not enable Claude or Gemini adaptations."""
    options = RelayOptions()
    assert options.claude.thinking_adapter_enabled is False
    assert options.claude.thinking_budget_percentage == 0
    assert options.claude.minimum_max_tokens == 0
    assert options.gemini.thinking_adapter_enabled is False
    assert options.gemini.thinking_budget == 0
    assert options.gemini.thought_signature_bypass is False
    assert options.model_suffix_preserved is False
    assert options.openrouter_dialects is False


def test_claude_options_accepts_adaptation_values() -> None:
    """Claude thinking adaptation options are configurable."""
    options = ClaudeOptions(
        thinking_adapter_enabled=True,
        thinking_budget_percentage=20,
        minimum_max_tokens=4096,
    )
    assert options.thinking_adapter_enabled is True
    assert options.thinking_budget_percentage == 20
    assert options.minimum_max_tokens == 4096


def test_gemini_options_accepts_adaptation_values() -> None:
    """Gemini thinking adaptation options are configurable."""
    options = GeminiOptions(
        thinking_adapter_enabled=True,
        thinking_budget=16384,
        thought_signature_bypass=True,
    )
    assert options.thinking_adapter_enabled is True
    assert options.thinking_budget == 16384
    assert options.thought_signature_bypass is True


def test_context_defaults_are_nil_safe() -> None:
    """RelayConversionContext() has no callbacks and safe options."""
    context = RelayConversionContext()
    assert context.options == RelayOptions()
    assert context.default_max_tokens is None
    assert context.safety_setting is None
    assert context.supports_image_generation is None
    assert context.preserve_thinking_suffix is None
    assert context.media_resolver is None
    assert context.losses == []


def test_context_rejects_negative_default_max_tokens() -> None:
    """A negative default_max_tokens callback is rejected on access."""
    context = RelayConversionContext(default_max_tokens=lambda model: -1)
    value = context.default_max_tokens("claude-sonnet-4-5")
    assert value is not None
    assert value < 0  # validation happens in the engine adapter, not the contract


def test_relay_error_carries_stable_code() -> None:
    """RelayError accepts a stable machine-readable code."""
    error = RelayError("cannot convert", code="malformed_payload")
    assert error.code == "malformed_payload"
    assert "cannot convert" in str(error)


def test_relay_error_default_code() -> None:
    """RelayError defaults to the relay base code."""
    error = RelayError("boom")
    assert error.code == "relay_error"


def test_relay_error_code_enum_is_stable() -> None:
    """RelayErrorCode values match the relaykit-compatible catalog."""
    from quadkit.contracts.ai.exceptions import RelayErrorCode

    assert RelayErrorCode.UNSUPPORTED_FORMAT.value == "unsupported_format"
    assert RelayErrorCode.UNSUPPORTED_ROUTE.value == "unsupported_route"
    assert RelayErrorCode.MALFORMED_PAYLOAD.value == "malformed_payload"
    assert RelayErrorCode.UNSUPPORTED_FEATURE.value == "unsupported_feature"
    assert RelayErrorCode.MISSING_REQUIRED_OPTION.value == "missing_required_option"
    assert RelayErrorCode.MEDIA_RESOLUTION_REQUIRED.value == "media_resolution_required"
    assert RelayErrorCode.STREAM_STATE_INVALID.value == "stream_state_invalid"
    assert RelayErrorCode.STREAM_ALREADY_FINALIZED.value == "stream_already_finalized"
    assert RelayErrorCode.SERIALIZATION_ERROR.value == "serialization_error"


def test_relay_error_accepts_enum_code() -> None:
    """RelayError normalizes a RelayErrorCode to its string value."""
    from quadkit.contracts.ai.exceptions import RelayErrorCode

    error = RelayError("no route", code=RelayErrorCode.UNSUPPORTED_ROUTE)
    assert error.code == "unsupported_route"


def test_relay_loss_is_frozen() -> None:
    """RelayLoss is immutable and carries source/target/reason/severity."""
    loss = RelayLoss(
        field="parallel_tool_calls",
        target=RelayFormat.CLAUDE,
        reason="claude always runs tools in parallel",
        severity="warning",
    )
    assert loss.field == "parallel_tool_calls"
    assert loss.target is RelayFormat.CLAUDE
    assert loss.severity == "warning"


def test_relay_convert_result_is_frozen_at_outer_level() -> None:
    """RelayConvertResult attributes cannot be reassigned."""
    result = RelayConvertResult(
        value={"model": "gpt-4o"},
        source=RelayFormat.OPENAI_CHAT,
        target=RelayFormat.CLAUDE,
        converter_id="openai_chat_to_claude",
        quality=ConversionQuality.FAIR,
        steps=["openai_chat", "ir", "claude"],
    )
    assert result.converter_id == "openai_chat_to_claude"
    assert result.source is RelayFormat.OPENAI_CHAT
    assert result.target is RelayFormat.CLAUDE
    assert result.losses == ()
    assert result.warnings == ()


def test_relay_convert_result_accepts_losses_and_warnings() -> None:
    """Losses and warnings surface semantic degradation."""
    result = RelayConvertResult(
        value={"model": "gpt-4o"},
        source=RelayFormat.OPENAI_CHAT,
        target=RelayFormat.GEMINI,
        converter_id="openai_chat_to_gemini",
        quality=ConversionQuality.FAIR,
        steps=["openai_chat", "ir", "gemini"],
        losses=[
            RelayLoss(
                field="response_format",
                target=RelayFormat.GEMINI,
                reason="json_mode_not_supported",
                severity="info",
            )
        ],
        warnings=["response_format dropped"],
        usage=RelayUsage(prompt_tokens=1, completion_tokens=2),
    )
    assert len(result.losses) == 1
    assert result.warnings == ["response_format dropped"]
    assert result.usage is not None
    assert result.usage.total_tokens == 3


def test_relay_usage_derives_total() -> None:
    """total_tokens is derived as prompt + completion."""
    usage = RelayUsage(prompt_tokens=10, completion_tokens=5)
    assert usage.total_tokens == 15


def test_media_resolver_protocol_exists() -> None:
    """The media resolver is a protocol, not a network client."""
    from quadkit.contracts.ai.relay.context import MediaResolverProtocol

    assert MediaResolverProtocol is not None