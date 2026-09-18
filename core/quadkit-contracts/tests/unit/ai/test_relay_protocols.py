"""Tests for the relay service protocols and payload unions."""
from __future__ import annotations

from typing import Any

from quadkit.contracts.ai.relay.types import (
    ConversionQuality,
    RelayConvertResult,
    RelayFormat,
)
from quadkit.contracts.ai.relay.ir import (
    RelayRequest,
    RelayResponse,
    StreamDelta,
)
from quadkit.contracts.ai.relay.dto import (
    ClaudeRequest,
    ClaudeResponse,
    GeminiRequest,
    GeminiResponse,
    OpenAIChatRequest,
    OpenAIChatResponse,
    ResponsesRequest,
    ResponsesResponse,
)
from quadkit.contracts.ai.relay.context import RelayConversionContext
from quadkit.contracts.ai.relay.protocols import (
    RelayConverterProtocol,
    RelayMapperProtocol,
    RelayRegistryProtocol,
    RelayStreamSessionProtocol,
)
from quadkit.contracts.core.result import Result


def test_relay_payload_unions_cover_all_dto_families() -> None:
    """Request and response payload unions include every wire DTO."""
    from quadkit.contracts.ai.relay.types import RelayRequestPayload, RelayResponsePayload

    assert OpenAIChatRequest in RelayRequestPayload.__args__
    assert ResponsesRequest in RelayRequestPayload.__args__
    assert ClaudeRequest in RelayRequestPayload.__args__
    assert GeminiRequest in RelayRequestPayload.__args__

    assert OpenAIChatResponse in RelayResponsePayload.__args__
    assert ResponsesResponse in RelayResponsePayload.__args__
    assert ClaudeResponse in RelayResponsePayload.__args__
    assert GeminiResponse in RelayResponsePayload.__args__


def test_converter_protocol_implementable_without_ai_llm() -> None:
    """A structural fake can implement RelayConverterProtocol."""

    class FakeConverter(RelayConverterProtocol):
        def convert_request(
            self,
            payload: Any,
            source: RelayFormat,
            target: RelayFormat,
            *,
            context: RelayConversionContext | None = None,
            registry: RelayRegistryProtocol | None = None,
        ) -> Result[RelayConvertResult[Any], Exception]:
            raise NotImplementedError

        def convert_response(
            self,
            payload: Any,
            source: RelayFormat,
            target: RelayFormat,
            *,
            context: RelayConversionContext | None = None,
            registry: RelayRegistryProtocol | None = None,
        ) -> Result[RelayConvertResult[Any], Exception]:
            raise NotImplementedError

        def new_stream_session(
            self,
            source: RelayFormat,
            target: RelayFormat,
            *,
            options: Any | None = None,
            context: RelayConversionContext | None = None,
            registry: RelayRegistryProtocol | None = None,
        ) -> Result[RelayStreamSessionProtocol, Exception]:
            raise NotImplementedError

        def convert_stream_chunk(
            self,
            session: RelayStreamSessionProtocol,
            event: Any,
        ) -> tuple[Any, ...]:
            return ()

        def finalize(
            self,
            session: RelayStreamSessionProtocol,
        ) -> tuple[Any, ...]:
            return ()

    fake = FakeConverter()
    assert isinstance(fake, RelayConverterProtocol)


def test_stream_session_protocol_implementable() -> None:
    """A structural fake can implement RelayStreamSessionProtocol."""

    class FakeSession(RelayStreamSessionProtocol):
        def accept(self, event: Any) -> tuple[Any, ...]:
            return ()

        def finalize(self) -> tuple[Any, ...]:
            return ()

        def snapshot(self) -> Any:
            return None

    session = FakeSession()
    assert isinstance(session, RelayStreamSessionProtocol)


def test_mapper_protocol_implementable() -> None:
    """A structural fake can implement RelayMapperProtocol."""

    class FakeMapper(RelayMapperProtocol):
        def request_to_ir(self, payload: Any) -> Any:
            return RelayRequest(model="m", messages=[])

        def ir_to_request(self, request: RelayRequest) -> Any:
            return {"model": request.model}

        def response_to_ir(self, payload: Any) -> Any:
            return RelayResponse(model="m")

        def ir_to_response(self, response: RelayResponse) -> Any:
            return {"model": response.model}

    mapper = FakeMapper()
    assert isinstance(mapper, RelayMapperProtocol)


def test_registry_protocol_implementable() -> None:
    """A structural fake can implement RelayRegistryProtocol."""

    class FakeRegistry(RelayRegistryProtocol):
        def mapper(self, source: RelayFormat, target: RelayFormat) -> Any | None:
            return None

        def converter_routes(self) -> tuple[tuple[RelayFormat, RelayFormat], ...]:
            """Return an empty supported-route set."""
            return ()

        def mapper_ids(self) -> tuple[str, ...]:
            """Return an empty mapper id set."""
            return ()

        def converter_version(self) -> str:
            """Return a fixed diagnostic version."""
            return "1.0.0"

        def route_quality(
            self, source: RelayFormat, target: RelayFormat
        ) -> ConversionQuality:
            """Return the static quality for the pair."""
            return ConversionQuality.GOOD if source is target else ConversionQuality.FAIR

    registry = FakeRegistry()
    assert isinstance(registry, RelayRegistryProtocol)
    assert registry.mapper(RelayFormat.CLAUDE, RelayFormat.GEMINI) is None


def test_stream_delta_has_granular_tool_and_status_fields() -> None:
    """StreamDelta carries event kind, tool fragments, and status."""
    delta = StreamDelta(
        content="Hi",
        kind="content",
        tool_call_index=0,
        tool_call_id="call_1",
        tool_call_arguments='{"a":',
        status="in_progress",
    )
    assert delta.kind == "content"
    assert delta.tool_call_index == 0
    assert delta.tool_call_id == "call_1"
    assert delta.tool_call_arguments == '{"a":'
    assert delta.status == "in_progress"