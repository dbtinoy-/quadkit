"""Tests for the relay gateway contracts (channels, requests, errors, protocols)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from quadkit.contracts.ai.relay import (
    RelayChannel,
    RelayGatewayError,
    RelayGatewayMetadata,
    RelayGatewayProtocol,
    RelayGatewayRequest,
    RelayGatewayResult,
    RelayUpstreamProtocol,
    RelayWireEvent,
    UpstreamChunk,
    UpstreamRequest,
    UpstreamResponse,
)
from quadkit.contracts.ai.relay.types import ConversionQuality, RelayFormat

PAYLOAD = {"messages": [{"role": "user", "content": "hi"}]}


def make_channel(**overrides: object) -> RelayChannel:
    params = {
        "name": "primary",
        "upstream_base_url": "https://api.example.com/v1",
        "target_format": RelayFormat.OPENAI_CHAT,
        "models": ("gpt-4o",),
    }
    params.update(overrides)
    return RelayChannel(**params)


def make_request(**overrides: object) -> RelayGatewayRequest:
    params = {
        "request_id": "req-1",
        "tenant_id": "tenant-1",
        "source": RelayFormat.OPENAI_CHAT,
        "model": "gpt-4o",
        "stream": False,
        "payload": PAYLOAD,
        "headers": {"authorization": "Bearer x"},
        "channel": make_channel(),
    }
    params.update(overrides)
    return RelayGatewayRequest(**params)


class TestRelayChannel:
    def test_valid_construction_defaults(self) -> None:
        channel = make_channel()
        assert channel.priority == 100
        assert channel.enabled is True
        assert channel.timeout_seconds == 60.0
        assert channel.capabilities == frozenset()
        assert channel.weight == 100

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError):
            make_channel(name="")

    def test_rejects_empty_upstream_base_url(self) -> None:
        with pytest.raises(ValueError):
            make_channel(upstream_base_url="")

    def test_rejects_empty_models(self) -> None:
        with pytest.raises(ValueError):
            make_channel(models=())

    def test_rejects_non_positive_timeout(self) -> None:
        with pytest.raises(ValueError):
            make_channel(timeout_seconds=0)
        with pytest.raises(ValueError):
            make_channel(timeout_seconds=-1.0)

    def test_weight_defaults_to_100(self) -> None:
        channel = make_channel()
        assert channel.weight == 100

    def test_weight_round_trip(self) -> None:
        channel = make_channel(weight=25)
        assert channel.weight == 25

    def test_zero_weight_is_valid(self) -> None:
        channel = make_channel(weight=0)
        assert channel.weight == 0

    def test_rejects_negative_weight(self) -> None:
        with pytest.raises(ValueError):
            make_channel(weight=-1)

    def test_endpoint_kinds_defaults_to_empty(self) -> None:
        channel = make_channel()
        assert channel.endpoint_kinds == frozenset()

    def test_endpoint_kinds_round_trip(self) -> None:
        channel = make_channel(endpoint_kinds=frozenset({"embeddings"}))
        assert channel.endpoint_kinds == frozenset({"embeddings"})

    def test_missing_target_format_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            RelayChannel(name="x", upstream_base_url="https://x", models=("m",))

    def test_model_map_defaults_to_empty(self) -> None:
        channel = make_channel()
        assert channel.model_map == {}

    def test_resolve_model_uses_alias_when_unmapped(self) -> None:
        channel = make_channel()
        assert channel.resolve_model("gpt-4o") == "gpt-4o"

    def test_resolve_model_uses_mapping_when_present(self) -> None:
        channel = make_channel(
            model_map={"gpt-4o": "gpt-4o-2024-11-20"},
        )
        assert channel.resolve_model("gpt-4o") == "gpt-4o-2024-11-20"
        assert channel.resolve_model("unknown-alias") == "unknown-alias"

    def test_rejects_model_map_keys_outside_models(self) -> None:
        with pytest.raises(ValueError, match="model_map"):
            make_channel(model_map={"other-model": "gpt-4o"})

    def test_frozen(self) -> None:
        channel = make_channel()
        with pytest.raises(FrozenInstanceError):
            channel.name = "x"


class TestUpstreamRequest:
    def test_channel_name_defaults_to_empty(self) -> None:
        request = UpstreamRequest(
            request_id="req-1",
            method="POST",
            url="https://upstream/v1/chat/completions",
            headers={"content-type": "application/json"},
            payload=PAYLOAD,
            timeout_seconds=60.0,
        )
        assert request.channel_name == ""

    def test_channel_name_round_trip(self) -> None:
        request = UpstreamRequest(
            request_id="req-1",
            method="POST",
            url="https://upstream/v1/chat/completions",
            headers={"content-type": "application/json"},
            payload=PAYLOAD,
            timeout_seconds=60.0,
            channel_name="primary",
        )
        assert request.channel_name == "primary"

    def test_construction_without_channel_name_keeps_working(self) -> None:
        request = UpstreamRequest(
            request_id="req-1",
            method="POST",
            url="https://upstream/v1/chat/completions",
            headers={"content-type": "application/json"},
            payload=PAYLOAD,
            timeout_seconds=60.0,
        )
        assert request.request_id == "req-1"
        assert request.method == "POST"
        assert request.url == "https://upstream/v1/chat/completions"
        assert request.headers == {"content-type": "application/json"}
        assert request.payload == PAYLOAD
        assert request.timeout_seconds == 60.0

    def test_frozen(self) -> None:
        request = UpstreamRequest(
            request_id="req-1",
            method="POST",
            url="https://upstream/v1/chat/completions",
            headers={"content-type": "application/json"},
            payload=PAYLOAD,
            timeout_seconds=60.0,
        )
        with pytest.raises(FrozenInstanceError):
            request.channel_name = "x"


class TestRelayGatewayRequest:
    def test_carries_all_fields(self) -> None:
        channel = make_channel()
        request = make_request(channel=channel)
        assert request.request_id == "req-1"
        assert request.tenant_id == "tenant-1"
        assert request.source == RelayFormat.OPENAI_CHAT
        assert request.model == "gpt-4o"
        assert request.stream is False
        assert request.headers == {"authorization": "Bearer x"}
        assert request.payload == PAYLOAD
        assert request.channel == channel

    def test_channel_snapshot_immutability(self) -> None:
        request = make_request()
        with pytest.raises(FrozenInstanceError):
            request.channel.name = "x"


class TestRelayGatewayResult:
    def test_defaults(self) -> None:
        result = RelayGatewayResult(status_code=200, headers={"x": "y"})
        assert result.payload is None
        assert result.stream is None
        assert result.metadata is None

    def test_holds_status_and_headers(self) -> None:
        result = RelayGatewayResult(status_code=429, headers={"retry-after": "5"})
        assert result.status_code == 429
        assert result.headers == {"retry-after": "5"}


class TestRelayGatewayError:
    def test_construct_and_attributes(self) -> None:
        error = RelayGatewayError(
            code="UPSTREAM_FAILED",
            message="boom",
            status_code=502,
            request_id="req-9",
            retryable=True,
        )
        assert error.code == "UPSTREAM_FAILED"
        assert error.message == "boom"
        assert error.status_code == 502
        assert error.request_id == "req-9"
        assert error.retryable is True

    def test_retryable_defaults_false(self) -> None:
        error = RelayGatewayError(
            code="UPSTREAM_FAILED", message="boom", status_code=502, request_id="req-9"
        )
        assert error.retryable is False

    def test_frozen(self) -> None:
        error = RelayGatewayError(
            code="UPSTREAM_FAILED", message="boom", status_code=502, request_id="req-9"
        )
        with pytest.raises(FrozenInstanceError):
            error.retryable = True

    def test_vars_exposes_only_public_fields(self) -> None:
        error = RelayGatewayError(
            code="UPSTREAM_FAILED", message="boom", status_code=502, request_id="req-9"
        )
        assert set(vars(error)) <= {
            "code",
            "message",
            "status_code",
            "request_id",
            "retryable",
        }
        assert {f.name for f in fields(error)} == {
            "code",
            "message",
            "status_code",
            "request_id",
            "retryable",
        }

    def test_raising_works(self) -> None:
        error = RelayGatewayError(
            code="UPSTREAM_FAILED", message="boom", status_code=502, request_id="req-9"
        )
        with pytest.raises(RelayGatewayError):
            raise error


class TestRelayGatewayProtocol:
    def test_implementing_stub_is_instance(self) -> None:
        class StubGateway:
            async def handle(self, request: RelayGatewayRequest) -> None:
                return None

        assert isinstance(StubGateway(), RelayGatewayProtocol)

    def test_non_implementing_is_not_instance(self) -> None:
        class MissingHandle:
            pass

        assert not isinstance(MissingHandle(), RelayGatewayProtocol)


class TestRelayUpstreamProtocol:
    def test_implementing_stub_is_instance(self) -> None:
        class StubUpstream:
            async def request(self, request: UpstreamRequest) -> UpstreamResponse:
                return UpstreamResponse(status_code=200, headers={}, payload=None)

            async def stream(self, request: UpstreamRequest):
                yield UpstreamChunk(event=None, data="x")

            async def cancel(self, request_id: str) -> None:
                return None

        assert isinstance(StubUpstream(), RelayUpstreamProtocol)

    def test_non_implementing_is_not_instance(self) -> None:
        class MissingMethods:
            pass

        assert not isinstance(MissingMethods(), RelayUpstreamProtocol)


class TestRelayGatewayMetadata:
    def test_fields_round_trip(self) -> None:
        metadata = RelayGatewayMetadata(
            converter_id="openai_chat_to_claude",
            source=RelayFormat.OPENAI_CHAT,
            target=RelayFormat.CLAUDE,
            quality=ConversionQuality.GOOD,
            loss_codes=("tool_calls",),
            warnings=("warning-1",),
        )
        assert metadata.converter_id == "openai_chat_to_claude"
        assert metadata.source == RelayFormat.OPENAI_CHAT
        assert metadata.target == RelayFormat.CLAUDE
        assert metadata.quality == ConversionQuality.GOOD
        assert metadata.loss_codes == ("tool_calls",)
        assert metadata.warnings == ("warning-1",)

    def test_defaults(self) -> None:
        metadata = RelayGatewayMetadata(
            converter_id="openai_chat_to_claude",
            source=RelayFormat.OPENAI_CHAT,
            target=RelayFormat.CLAUDE,
            quality=ConversionQuality.GOOD,
        )
        assert metadata.loss_codes == ()
        assert metadata.warnings == ()


class TestRelayPackageExports:
    def test_new_names_reexported_from_package(self) -> None:
        import quadkit.contracts.ai.relay as relay

        assert relay.RelayChannel is RelayChannel
        assert relay.RelayGatewayError is RelayGatewayError
        assert relay.RelayGatewayMetadata is RelayGatewayMetadata
        assert relay.RelayGatewayProtocol is RelayGatewayProtocol
        assert relay.RelayGatewayRequest is RelayGatewayRequest
        assert relay.RelayGatewayResult is RelayGatewayResult
        assert relay.RelayUpstreamProtocol is RelayUpstreamProtocol
        assert relay.RelayWireEvent is RelayWireEvent
        assert relay.UpstreamChunk is UpstreamChunk
        assert relay.UpstreamRequest is UpstreamRequest
        assert relay.UpstreamResponse is UpstreamResponse
