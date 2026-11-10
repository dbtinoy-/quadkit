"""Unit tests for typed_responses module."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.structured.typed_responses import (
    AudioResponseAdapter,
    AudioTranscription,
    FunctionCall,
    FunctionCallResponseAdapter,
    JSONResponseAdapter,
    ResponseType,
    StructuredData,
    StructuredResponseAdapter,
    TextResponseAdapter,
    TypedResponse,
    TypedResponseFactory,
)

# ── Data classes ─────────────────────────────────────────────────────

class TestDataClasses:
    def test_function_call_defaults(self) -> None:
        fc = FunctionCall(function_name="search")
        assert fc.function_name == "search"
        assert fc.arguments == {}
        assert fc.raw_content == ""

    def test_structured_data(self) -> None:
        sd = StructuredData(data={"key": "val"}, schema="my_schema")
        assert sd.data == {"key": "val"}
        assert sd.schema == "my_schema"

    def test_audio_transcription(self) -> None:
        at = AudioTranscription(text="Hello world", language="en", confidence=0.95)
        assert at.text == "Hello world"
        assert at.language == "en"
        assert at.confidence == 0.95

    def test_typed_response(self) -> None:
        tr = TypedResponse(
            response_type=ResponseType.TEXT,
            payload="hi",
            raw_content="hi",
        )
        assert tr.parse_success is True
        assert tr.parse_error is None

    def test_response_type_enum(self) -> None:
        assert ResponseType.TEXT.value == "text"
        assert ResponseType.JSON.value == "json"
        assert ResponseType.FUNCTION_CALL.value == "function_call"


# ── TextResponseAdapter ─────────────────────────────────────────────

class TestTextAdapter:
    @pytest.mark.asyncio
    async def test_parse_text(self) -> None:
        adapter = TextResponseAdapter()
        result = await adapter.parse("Hello world")
        assert result.response_type == ResponseType.TEXT
        assert result.payload == "Hello world"
        assert result.parse_success is True


# ── JSONResponseAdapter ──────────────────────────────────────────────

class TestJSONAdapter:
    @pytest.mark.asyncio
    async def test_parse_raw_json(self) -> None:
        adapter = JSONResponseAdapter()
        result = await adapter.parse('{"name": "Alice", "age": 30}')
        assert result.parse_success is True
        assert result.payload["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_parse_json_in_code_block(self) -> None:
        adapter = JSONResponseAdapter()
        content = '```json\n{"key": "value"}\n```'
        result = await adapter.parse(content)
        assert result.parse_success is True
        assert result.payload["key"] == "value"

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, capsys) -> None:
        adapter = JSONResponseAdapter()
        secret = "TYPED_JSON_SECRET_SENTINEL"
        result = await adapter.parse(f"invalid response {secret}")
        assert result.parse_success is False
        assert result.parse_error is not None
        assert secret not in result.parse_error
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err


# ── FunctionCallResponseAdapter ──────────────────────────────────────

class TestFunctionCallAdapter:
    @pytest.mark.asyncio
    async def test_parse_json_format(self) -> None:
        adapter = FunctionCallResponseAdapter()
        content = '{"function": "search", "arguments": {"query": "test"}}'
        result = await adapter.parse(content)
        assert result.parse_success is True
        assert isinstance(result.payload, FunctionCall)
        assert result.payload.function_name == "search"
        assert result.payload.arguments["query"] == "test"

    @pytest.mark.asyncio
    async def test_parse_regex_format(self) -> None:
        adapter = FunctionCallResponseAdapter()
        content = 'search(query="hello")'
        result = await adapter.parse(content)
        assert result.parse_success is True
        assert isinstance(result.payload, FunctionCall)
        assert result.payload.function_name == "search"

    @pytest.mark.asyncio
    async def test_parse_unparseable(self) -> None:
        adapter = FunctionCallResponseAdapter()
        content = "just some random text with no function"
        result = await adapter.parse(content)
        assert result.parse_success is False


# ── StructuredResponseAdapter ────────────────────────────────────────

class TestStructuredAdapter:
    @pytest.mark.asyncio
    async def test_parse_json_object(self) -> None:
        adapter = StructuredResponseAdapter(schema="user")
        content = '{"name": "Bob", "role": "admin"}'
        result = await adapter.parse(content)
        assert result.parse_success is True
        assert isinstance(result.payload, StructuredData)
        assert result.payload.data["name"] == "Bob"
        assert result.payload.schema == "user"

    @pytest.mark.asyncio
    async def test_parse_no_json_found(self) -> None:
        adapter = StructuredResponseAdapter()
        result = await adapter.parse("no json here")
        assert result.parse_success is False
        assert "No JSON" in result.parse_error

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, capsys) -> None:
        adapter = StructuredResponseAdapter()
        secret = "TYPED_STRUCTURED_SECRET_SENTINEL"
        result = await adapter.parse(f'{{"value": "{secret}", invalid}}')
        assert result.parse_success is False
        assert result.parse_error is not None
        assert secret not in result.parse_error
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err


# ── AudioResponseAdapter ────────────────────────────────────────────

class TestAudioAdapter:
    @pytest.mark.asyncio
    async def test_parse_json_transcription(self) -> None:
        adapter = AudioResponseAdapter()
        content = '{"text": "Hello", "language": "en", "confidence": 0.9}'
        result = await adapter.parse(content)
        assert result.parse_success is True
        assert isinstance(result.payload, AudioTranscription)
        assert result.payload.text == "Hello"
        assert result.payload.language == "en"

    @pytest.mark.asyncio
    async def test_parse_plain_text_fallback(self) -> None:
        adapter = AudioResponseAdapter()
        result = await adapter.parse("Just plain transcription text")
        assert result.parse_success is True
        assert isinstance(result.payload, AudioTranscription)
        assert result.payload.text == "Just plain transcription text"


# ── TypedResponseFactory ─────────────────────────────────────────────

class TestFactory:
    def test_get_text_adapter(self) -> None:
        factory = TypedResponseFactory()
        adapter = factory.get_adapter(ResponseType.TEXT)
        assert isinstance(adapter, TextResponseAdapter)

    def test_get_json_adapter(self) -> None:
        factory = TypedResponseFactory()
        adapter = factory.get_adapter(ResponseType.JSON)
        assert isinstance(adapter, JSONResponseAdapter)

    def test_get_structured_adapter(self) -> None:
        factory = TypedResponseFactory()
        adapter = factory.get_adapter(ResponseType.STRUCTURED, schema="user_schema")
        assert isinstance(adapter, StructuredResponseAdapter)

    def test_register_custom(self) -> None:
        factory = TypedResponseFactory()
        custom = TextResponseAdapter()
        factory.register_adapter(ResponseType.TEXT, custom)
        assert factory.get_adapter(ResponseType.TEXT) is custom
