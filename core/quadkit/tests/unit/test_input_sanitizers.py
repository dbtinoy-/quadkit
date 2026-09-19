"""Tests for the input sanitizers: InputSanitizer facade, filename/SQL-LIKE,
URL/path/SSRF guards, and the HTML sanitizer branches."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.security.config import InputSanitizerConfig
from quadkit.security.sanitization.filename import FilenameSanitizer
from quadkit.security.sanitization.html import HtmlSanitizer
from quadkit.security.sanitization.sanitizer import InputSanitizer
from quadkit.security.sanitization.url import UrlSanitizer

# ── Filename / SQL LIKE ───────────────────────────────────────────────────


def test_filename_sanitizer() -> None:
    s = FilenameSanitizer()
    assert s.sanitize_filename("") == ""
    # Traversal slashes are stripped, leaving a dot-leading name → renamed.
    assert s.sanitize_filename("../../etc/passwd") == "unnamed_file"
    assert s.sanitize_filename("a b/c\\d*e.f") == "a_bcd_e.f"
    # Dot-leading results are replaced.
    assert s.sanitize_filename("..") == "unnamed_file"
    assert s.sanitize_filename("good-name.txt") == "good-name.txt"


def test_sql_like_sanitizer() -> None:
    s = FilenameSanitizer()
    assert s.sanitize_sql_like("") == ""
    assert s.sanitize_sql_like("100%") == "100\\%"
    assert s.sanitize_sql_like("a_b") == "a\\_b"
    assert s.sanitize_sql_like("back\\slash") == "back\\\\slash"
    # Custom escape character.
    assert s.sanitize_sql_like("50%", escape_char="#") == "50#%"


# ── URL / path / SSRF ─────────────────────────────────────────────────────


def test_url_sanitizer_dangerous_schemes() -> None:
    s = UrlSanitizer()
    assert s.sanitize_url("") == ""
    assert s.sanitize_url("https://example.com/x") == "https://example.com/x"
    assert s.sanitize_url("javascript:alert(1)") == ""
    assert s.sanitize_url("JaVaScRiPt:alert(1)") == ""
    assert s.sanitize_url("  javascript:alert(1)") == ""  # leading whitespace
    assert s.sanitize_url("data:text/html;base64,xxx") == ""
    assert s.sanitize_url("file:///etc/passwd") == ""
    assert s.sanitize_url("vbscript:msgbox") == ""


def test_url_sanitizer_path_traversal() -> None:
    s = UrlSanitizer()
    assert s.sanitize_path("") == ""
    assert s.sanitize_path("a/b.txt") == "a/b.txt"
    assert s.sanitize_path("../etc/passwd") == "etc/passwd"
    assert s.sanitize_path("a/../../b") == "a/b"
    assert s.sanitize_path("..") == ""
    assert s.sanitize_path("a\x00b.txt") == "ab.txt"
    # Repeated traversal collapses fully (loop until stable).
    assert s.sanitize_path("../../../x") == "x"


def test_url_sanitizer_ssrf_check_with_resolver() -> None:
    s = UrlSanitizer()

    # Private IP literal → unsafe.
    assert s.is_safe_url_for_request("http://127.0.0.1/x") is False
    assert s.is_safe_url_for_request("http://10.0.0.1/x") is False
    assert s.is_safe_url_for_request("http://192.168.1.1/x") is False

    # Injectable resolver: public IP → safe, private → unsafe.
    import ipaddress

    def resolver(host: str) -> list[Any]:
        return (
            [ipaddress.ip_address("93.184.216.34")]
            if host == "public.example"
            else [ipaddress.ip_address("169.254.1.1")]
        )

    assert s.is_safe_url_for_request("http://public.example/", resolver=resolver) is True
    assert s.is_safe_url_for_request("http://link.local/", resolver=resolver) is False


# ── InputSanitizer facade ─────────────────────────────────────────────────


def test_facade_delegates_to_sub_sanitizers() -> None:
    facade = InputSanitizer()
    assert facade.config is not None

    assert facade.sanitize_filename("a b.txt") == "a_b.txt"
    assert facade.sanitize_sql_like("50%") == "50\\%"
    assert facade.sanitize_url("javascript:x") == ""
    assert facade.sanitize_path("../x") == "x"
    assert facade.is_safe_url_for_request("http://127.0.0.1") is False


def test_facade_header_value_crlf() -> None:
    facade = InputSanitizer()
    assert facade.sanitize_header_value("") == ""
    assert facade.sanitize_header_value("plain") == "plain"
    # CRLF injection neutralised.
    # Each CR/LF char is replaced with a space.
    assert facade.sanitize_header_value("ok\r\nX-Injected: 1") == "ok  X-Injected: 1"


def test_facade_sanitize_modes() -> None:
    # Default mode (allow) removes dangerous tags (regex-based, no nh3 needed).
    default = InputSanitizer()
    assert default.sanitize("<script>alert(1)</script>hi") == "hi"
    assert default.sanitize("") == ""

    # Escape mode.
    esc = InputSanitizer(InputSanitizerConfig(default_sanitize_mode="escape"))
    assert esc.sanitize("<b>&") == "&lt;b&gt;&amp;"

    # Unknown mode passes through.
    passthrough = InputSanitizer(InputSanitizerConfig(default_sanitize_mode="bogus"))
    assert passthrough.sanitize("<b>x</b>") == "<b>x</b>"


def test_facade_strip_mode_needs_nh3() -> None:
    from quadkit.security.sanitization.html import _NH3_AVAILABLE

    strip = InputSanitizer(InputSanitizerConfig(default_sanitize_mode="strip"))
    if _NH3_AVAILABLE:
        assert strip.sanitize("<b>bold</b>") == "bold"
    else:
        with pytest.raises(ImportError, match="nh3"):
            strip.sanitize("<b>bold</b>")


def test_facade_sanitize_dict_recursion() -> None:
    facade = InputSanitizer(InputSanitizerConfig(default_sanitize_mode="escape"))
    data: dict[str, Any] = {
        "a": "<b>",
        "nested": {"b": "<i>"},
        "list": ["<u>", 42],
        "int": 7,
        "none": None,
    }
    out = facade.sanitize_dict(data)
    assert out["a"] == "&lt;b&gt;"
    assert out["nested"]["b"] == "&lt;i&gt;"
    assert out["list"] == ["&lt;u&gt;", 42]
    assert out["int"] == 7
    assert out["none"] is None
    # Empty dict passes through unchanged.
    assert facade.sanitize_dict({}) == {}


# ── HTML sanitizer branches ───────────────────────────────────────────────


def test_html_sanitizer_strip_and_escape() -> None:
    from quadkit.security.sanitization.html import _NH3_AVAILABLE

    html = HtmlSanitizer(InputSanitizerConfig())
    assert html.escape_html("") == ""
    assert html.escape_html("<a>&'\"") == "&lt;a&gt;&amp;&#x27;&quot;"
    if _NH3_AVAILABLE:
        assert html.strip_html("<script>bad</script><b>ok</b>") == "ok"
    else:
        with pytest.raises(ImportError, match="nh3"):
            html.strip_html("<b>ok</b>")


def test_html_sanitizer_strip_dangerous_keeps_safe_tags() -> None:
    html = HtmlSanitizer(InputSanitizerConfig())
    out = html.strip_dangerous("<b>bold</b><iframe src=x></iframe>")
    assert "<b>bold</b>" in out
    assert "iframe" not in out
