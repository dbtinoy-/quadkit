"""The render-trust boundary: attribution, immutability, and JSON embedding.

``TrustedHTML`` records *who* vouched for a value. It cannot verify that the
grant was correct, so the tests that matter most here are the ones covering
:func:`json_for_html` — the helper that exists specifically so callers cannot
serialize JSON into HTML and mark it trusted without escaping it first.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json as stdlib_json
import re

import pytest

from quadkit.primitives.trusted_html import (
    TrustedHTML,
    escape_json_for_html,
    json_for_html,
    trusted_html,
    trusted_static_script,
    trusted_svg_icon,
    trusted_template_output,
)


def _dumps(value: object) -> str:
    return stdlib_json.dumps(value, default=str, ensure_ascii=False)


class TestTrustedHTMLCapability:
    def test_is_a_str_and_renders_verbatim(self) -> None:
        value = trusted_html("<b>hi</b>", source="test")
        assert isinstance(value, str)
        assert value.__html__() == "<b>hi</b>"

    def test_requires_a_non_empty_source(self) -> None:
        with pytest.raises(ValueError, match="non-empty source"):
            TrustedHTML("<b>hi</b>", "   ")

    def test_rejects_non_string_values(self) -> None:
        with pytest.raises(TypeError, match="must be a string"):
            TrustedHTML(object(), "test")  # type: ignore[arg-type]

    def test_is_immutable(self) -> None:
        value = trusted_html("<b>hi</b>", source="test")
        with pytest.raises(FrozenInstanceError):
            value.source = "someone else"  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("factory", "kwargs", "expected"),
        [
            (trusted_template_output, {"template": "page.html"}, "template output"),
            (trusted_svg_icon, {"name": "check"}, "owned SVG icon"),
            (trusted_static_script, {"asset": "app.js"}, "static script"),
        ],
    )
    def test_grant_helpers_record_their_provenance(
        self, factory: object, kwargs: dict[str, str], expected: str
    ) -> None:
        value = factory("<b>x</b>", **kwargs)  # type: ignore[operator]
        assert expected in value.source


class TestJSONForHTML:
    """JSON is not safe to embed in HTML verbatim."""

    def test_escapes_script_breakout(self) -> None:
        payload = "</script><img src=x onerror=alert(1)>"
        result = json_for_html({"n": payload}, source="test", dumps=_dumps)

        assert "</script>" not in result
        assert "\\u003c" in result

    def test_escaping_is_lossless(self) -> None:
        """Escapes are JSON \\uXXXX sequences, so the parsed value is unchanged."""
        payload = "</script>&<>\u2028\u2029 ok"
        result = json_for_html({"n": payload}, source="test", dumps=_dumps)

        assert stdlib_json.loads(result)["n"] == payload

    def test_escapes_js_line_separators(self) -> None:
        """U+2028/U+2029 are valid in JSON but terminate JavaScript lines."""
        result = json_for_html({"n": "a\u2028b\u2029c"}, source="test", dumps=_dumps)

        assert "\u2028" not in result
        assert "\u2029" not in result
        assert "\\u2028" in result and "\\u2029" in result

    def test_escapes_ampersand(self) -> None:
        result = json_for_html({"n": "a&b"}, source="test", dumps=_dumps)

        assert "&" not in result
        assert "\\u0026" in result

    def test_result_is_trusted_and_attributed(self) -> None:
        result = json_for_html({"a": 1}, source="my caller", dumps=_dumps)

        assert isinstance(result, TrustedHTML)
        assert "my caller" in result.source

    def test_survives_embedding_in_a_script_element(self) -> None:
        """The end-to-end property the helper exists to guarantee."""
        payload = "</script><img src=x onerror=alert(1)>"
        embedded = json_for_html({"n": payload}, source="test", dumps=_dumps)
        document = f"<script>window.S = {embedded};</script>"

        # Exactly one closing tag: the one we wrote.
        assert document.count("</script>") == 1

        match = re.search(r"window\.S = (.*);</script>", document)
        assert match is not None
        assert stdlib_json.loads(match.group(1))["n"] == payload

    def test_serializer_is_injected(self) -> None:
        """``primitives`` must not depend on a serialization implementation."""
        result = json_for_html(
            {"a": 1}, source="test", dumps=lambda _: '{"replaced":true}'
        )

        assert stdlib_json.loads(result) == {"replaced": True}


class TestEscapeJSONForHTML:
    def test_grants_no_trust(self) -> None:
        """The escaping primitive returns a plain str, so autoescape applies."""
        result = escape_json_for_html('{"a":"<b>"}')

        assert not isinstance(result, TrustedHTML)
        assert result == '{"a":"\\u003cb\\u003e"}'

    def test_is_idempotent_on_already_escaped_text(self) -> None:
        once = escape_json_for_html('{"a":"<b>"}')

        assert escape_json_for_html(once) == once
