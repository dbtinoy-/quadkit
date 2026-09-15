"""Tests for serialization/negotiator.py — ContentNegotiator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.web.serialization.negotiator import ContentNegotiator, get_negotiator
from quadkit.web.serialization.serializers import (
    HTMLSerializer,
    JSONSerializer,
    PlainTextSerializer,
    ResponseSerializer,
    XMLSerializer,
)


def _make_request(accept: str = "*/*") -> MagicMock:
    req = MagicMock()
    req.headers = {"accept": accept}
    return req


class TestContentNegotiatorInit:
    def test_default_registers_builtin_serializers(self) -> None:
        neg = ContentNegotiator()
        assert "application/json" in neg._serializers
        assert "text/html" in neg._serializers
        assert "text/plain" in neg._serializers

    def test_custom_serializers_registered(self) -> None:
        custom = MagicMock()  # Don't use spec=ResponseSerializer; that is the orchestrator class
        custom.supported_types.return_value = ["application/x-custom"]
        neg = ContentNegotiator(serializers=[custom])
        assert "application/x-custom" in neg._serializers

    def test_add_serializer(self) -> None:
        neg = ContentNegotiator()
        custom = MagicMock()
        custom.supported_types.return_value = ["application/x-vendor"]
        neg.add_serializer(custom)
        assert "application/x-vendor" in neg._serializers


class TestContentNegotiatorNegotiate:
    def test_negotiates_json_for_json_accept(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/json")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_negotiates_html_for_text_html(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("text/html")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, HTMLSerializer)

    def test_negotiates_plain_text(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("text/plain")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, PlainTextSerializer)

    def test_negotiates_xml(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/xml")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, XMLSerializer)

    def test_wildcard_falls_back_to_json(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("*/*")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_type_wildcard_text_star(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("text/*")
        serializer = neg.negotiate(req)
        # Should match any text/* type (e.g. text/html or text/plain)
        assert serializer is not None

    def test_q_value_sorting(self) -> None:
        """Highest q-value should win."""
        neg = ContentNegotiator()
        req = _make_request("text/html;q=0.5, application/json;q=1.0")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_q_value_html_preferred(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/json;q=0.1, text/html;q=0.9")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, HTMLSerializer)

    def test_default_q_is_1_0(self) -> None:
        """No q= token → implicitly q=1.0, should be chosen over explicit q<1.0."""
        neg = ContentNegotiator()
        req = _make_request("application/json, text/html;q=0.5")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_no_match_defaults_to_json(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/x-unknown-type")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_empty_accept_parts_skipped(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/json, , text/plain")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)

    def test_q_value_invalid_float_falls_back_to_1(self) -> None:
        neg = ContentNegotiator()
        req = _make_request("application/json;q=bad")
        serializer = neg.negotiate(req)
        assert isinstance(serializer, JSONSerializer)


class TestContentNegotiatorSerialize:
    @pytest.mark.asyncio
    async def test_serialize_calls_serializer(self) -> None:
        mock_response = MagicMock()
        mock_serializer = MagicMock()
        mock_serializer.supported_types.return_value = ["application/json"]
        mock_serializer.serialize = AsyncMock(return_value=mock_response)

        neg = ContentNegotiator(serializers=[mock_serializer])
        req = _make_request("application/json")
        result = await neg.serialize({"key": "val"}, req)
        assert result is mock_response
        mock_serializer.serialize.assert_awaited_once()


class TestGetNegotiator:
    def test_returns_content_negotiator_instance(self) -> None:
        # get_resolver is imported inside the function — patch at the source
        with patch("quadkit.di.resolution.context.get_resolver", return_value=None):
            from quadkit.web.serialization import negotiator as neg_module
            # Reset the global
            neg_module._default_negotiator = None
            result = get_negotiator()
        assert isinstance(result, ContentNegotiator)

    def test_caches_default_negotiator(self) -> None:
        with patch("quadkit.di.resolution.context.get_resolver", return_value=None):
            from quadkit.web.serialization import negotiator as neg_module
            neg_module._default_negotiator = None
            first = get_negotiator()
            second = get_negotiator()
        assert first is second

    def test_uses_resolver_when_available(self) -> None:
        mock_resolver = MagicMock()
        mock_neg = ContentNegotiator()
        mock_resolver.resolve_sync.return_value = mock_neg
        with patch(
            "quadkit.di.resolution.context.get_resolver",
            return_value=mock_resolver,
        ):
            result = get_negotiator()
        assert result is mock_neg
