"""Unit tests for quadkit.ai.llm.structured.extractor (StructuredExtractor)."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.exceptions import (
    ExtractionMaxRetriesError,
    LLMError,
)
from quadkit.ai.llm.structured.extractor import StructuredExtractor, _get_content
from quadkit.contracts.ai.multimodal import ImageBase64Part, TextPart
from quadkit.result import Err, Ok

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel

    class _Item(BaseModel):
        name: str
        count: int

    _PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYDANTIC_AVAILABLE = False
    _Item = None  # type: ignore[assignment,misc]


@dataclasses.dataclass
class _Tag:
    label: str
    confidence: float


def _make_completion(content: str) -> MagicMock:
    """Create a mock Completion-like object."""
    comp = MagicMock()
    comp.content = content
    return comp


def _make_client(responses: list[str]) -> MagicMock:
    """Create a mock LLMClientProtocol that returns ``responses`` in sequence."""
    client = MagicMock()
    client.complete = AsyncMock(
        side_effect=[Ok(_make_completion(r)) for r in responses]
    )
    return client


def _make_error_client(exc: Exception) -> MagicMock:
    """Create a mock LLMClientProtocol whose complete() returns Err."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=Err(exc))
    return client


# ---------------------------------------------------------------------------
# _get_content helper
# ---------------------------------------------------------------------------


class TestGetContent:
    """Tests for the module-level _get_content() helper."""

    def test_string_passthrough(self):
        assert _get_content("hello") == "hello"

    def test_dict_content_key(self):
        assert _get_content({"content": "world"}) == "world"

    def test_dict_text_key_fallback(self):
        assert _get_content({"text": "fallback"}) == "fallback"

    def test_object_with_content_attr(self):
        obj = MagicMock()
        obj.content = "from attr"
        assert _get_content(obj) == "from attr"

    def test_unrecognised_raises_value_error(self):
        class _Opaque:
            pass

        with pytest.raises(ValueError, match="Cannot extract text content"):
            _get_content(_Opaque())


# ---------------------------------------------------------------------------
# StructuredExtractor — initialisation
# ---------------------------------------------------------------------------


class TestStructuredExtractorInit:
    """Tests for StructuredExtractor.__init__()."""

    def test_defaults(self):
        client = MagicMock()
        se = StructuredExtractor(client)
        assert se._client is client
        assert se._default_model is None
        assert se._default_max_retries == 2

    def test_custom_params(self):
        client = MagicMock()
        se = StructuredExtractor(client, default_model="gpt-4o", default_max_retries=5)
        assert se._default_model == "gpt-4o"
        assert se._default_max_retries == 5


# ---------------------------------------------------------------------------
# StructuredExtractor — _build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    """Tests for StructuredExtractor._build_messages()."""

    def test_string_prompt_produces_two_messages(self):
        msgs = StructuredExtractor._build_messages("hello", "system text")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[0].content == "system text"
        assert msgs[1].role == "user"
        assert msgs[1].content == "hello"

    def test_list_prompt_no_system_prepends(self):
        prompt_list = [{"role": "user", "content": "q"}]
        msgs = StructuredExtractor._build_messages(prompt_list, "sys")
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"

    def test_list_prompt_with_system_combines(self):
        prompt_list = [
            {"role": "system", "content": "existing"},
            {"role": "user", "content": "q"},
        ]
        msgs = StructuredExtractor._build_messages(prompt_list, "injection")
        system_msgs = [m for m in msgs if m.role == "system"]
        assert len(system_msgs) == 1
        assert "existing" in system_msgs[0].content
        assert "injection" in system_msgs[0].content

    def test_list_prompt_with_object_messages(self):
        """Works with objects that have .role / .content attributes."""
        msg = MagicMock()
        msg.role = "user"
        msg.content = "object prompt"
        msgs = StructuredExtractor._build_messages([msg], "sys")
        assert any(m.role == "user" for m in msgs)

    def test_list_prompt_preserves_multimodal_content(self):
        parts = [
            TextPart(text="describe this"),
            ImageBase64Part(data="Zm9v", media_type="image/png"),
        ]
        prompt_list = [{"role": "user", "content": parts}]

        msgs = StructuredExtractor._build_messages(prompt_list, "sys")

        user_msg = next(m for m in msgs if m.role == "user")
        assert user_msg.content == parts

    def test_list_prompt_with_object_message_preserves_multimodal_content(self):
        parts = [
            TextPart(text="describe this"),
            ImageBase64Part(data="Zm9v", media_type="image/png"),
        ]
        msg = MagicMock()
        msg.role = "user"
        msg.content = parts

        msgs = StructuredExtractor._build_messages([msg], "sys")

        user_msg = next(m for m in msgs if m.role == "user")
        assert user_msg.content == parts


# ---------------------------------------------------------------------------
# StructuredExtractor — extract() success paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStructuredExtractorExtract:
    """Integration-style tests for StructuredExtractor.extract()."""

    @pytest.mark.skipif(not _PYDANTIC_AVAILABLE, reason="pydantic not installed")
    async def test_success_first_attempt_pydantic(self):
        client = _make_client(['{"name": "widget", "count": 5}'])
        se = StructuredExtractor(client, default_max_retries=0)
        result = await se.extract("prompt", _Item)
        assert result.is_ok()
        item = result.unwrap()
        assert item.name == "widget"
        assert item.count == 5

    async def test_success_first_attempt_dataclass(self):
        client = _make_client(['{"label": "sports", "confidence": 0.85}'])
        se = StructuredExtractor(client, default_max_retries=0)
        result = await se.extract("classify this", _Tag)
        assert result.is_ok()
        tag = result.unwrap()
        assert tag.label == "sports"
        assert tag.confidence == pytest.approx(0.85)

    async def test_success_after_retry(self):
        """First response is invalid JSON, second is valid."""
        client = _make_client([
            "sorry, here it is: not json",
            '{"label": "tech", "confidence": 0.7}',
        ])
        se = StructuredExtractor(client, default_max_retries=1)
        result = await se.extract("prompt", _Tag)
        assert result.is_ok()
        assert result.unwrap().label == "tech"

    async def test_retry_logs_omit_model_and_schema_identifiers(self, monkeypatch):
        import quadkit.ai.llm.structured.extractor as extractor_module
        from pydantic import create_model

        private_model_name = "private-provider-model-tenant-42"
        private_schema_name = "PrivateTenant42Schema"
        private_schema = create_model(private_schema_name, value=(str, ...))
        client = _make_client(["not json", '{"value":"ok"}'])
        logger = MagicMock()
        monkeypatch.setattr(extractor_module, "logger", logger)
        se = StructuredExtractor(
            client, default_model=private_model_name, default_max_retries=1
        )

        result = await se.extract("prompt", private_schema)

        assert result.is_ok()
        logged = repr(logger.mock_calls)
        assert private_model_name not in logged
        assert private_schema_name not in logged

    async def test_fenced_json_response_succeeds(self):
        client = _make_client(['```json\n{"label": "news", "confidence": 0.5}\n```'])
        se = StructuredExtractor(client, default_max_retries=0)
        result = await se.extract("prompt", _Tag)
        assert result.is_ok()

    async def test_model_override_passed_to_client(self):
        client = _make_client(['{"label": "x", "confidence": 1.0}'])
        se = StructuredExtractor(client, default_model="gpt-3.5", default_max_retries=0)
        await se.extract("p", _Tag, model="gpt-4o")
        call_kwargs = client.complete.call_args[1]
        assert call_kwargs.get("model") == "gpt-4o"

    async def test_default_model_passed_to_client(self):
        client = _make_client(['{"label": "x", "confidence": 1.0}'])
        se = StructuredExtractor(client, default_model="gpt-3.5", default_max_retries=0)
        await se.extract("p", _Tag)
        call_kwargs = client.complete.call_args[1]
        assert call_kwargs.get("model") == "gpt-3.5"

    async def test_dict_type_output_model(self):
        client = _make_client(['{"anything": "goes"}'])
        se = StructuredExtractor(client, default_max_retries=0)
        result = await se.extract("p", dict)
        assert result.is_ok()
        assert result.unwrap() == {"anything": "goes"}


# ---------------------------------------------------------------------------
# StructuredExtractor — extract() failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestStructuredExtractorFailures:
    """Tests for failure scenarios in StructuredExtractor.extract()."""

    async def test_all_retries_exhausted_parse_error(self, capsys):
        """Parse failures do not expose raw model responses in logs or errors."""
        secret = "STRUCTURED_PARSE_SECRET_SENTINEL"
        client = _make_client([f"not json {secret}"] * 3)
        se = StructuredExtractor(client, default_max_retries=2)
        result = await se.extract("prompt", _Tag)
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ExtractionMaxRetriesError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.skipif(not _PYDANTIC_AVAILABLE, reason="pydantic not installed")
    async def test_all_retries_exhausted_validation_error(self, capsys):
        """Validation failures do not expose rejected values in logs or errors."""
        secret = "STRUCTURED_VALIDATION_SECRET_SENTINEL"
        bad = f'{{"name": "{secret}", "count": "{secret}"}}'
        client = _make_client([bad, bad])
        se = StructuredExtractor(client, default_max_retries=1)
        result = await se.extract("prompt", _Item)
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ExtractionMaxRetriesError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    async def test_llm_error_surfaces_immediately(self):
        """A recoverable LLM error is returned directly, with no retry."""
        secret = "STRUCTURED_LLM_ERROR_SECRET_SENTINEL"
        client = _make_error_client(LLMError(secret))
        se = StructuredExtractor(client, default_max_retries=3)
        result = await se.extract("prompt", _Tag)
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, LLMError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        assert error.details == {"error_type": "LLMError"}
        # Should have called complete exactly once — no retry on LLM errors
        assert client.complete.call_count == 1

    async def test_zero_retries_single_attempt(self):
        client = _make_client(["invalid json !!"])
        se = StructuredExtractor(client, default_max_retries=0)
        result = await se.extract("prompt", _Tag)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ExtractionMaxRetriesError)
        assert client.complete.call_count == 1

    async def test_max_retries_override(self):
        """Per-call max_retries=0 should limit to one attempt."""
        client = _make_client(["bad json", "good json?"])
        se = StructuredExtractor(client, default_max_retries=5)
        result = await se.extract("prompt", _Tag, max_retries=0)
        assert result.is_err()
        assert client.complete.call_count == 1
