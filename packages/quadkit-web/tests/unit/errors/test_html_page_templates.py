"""Tests for the debug error page HTML template builders."""

from __future__ import annotations

from quadkit.web.errors.html_page_templates import (
    _h,
    _method_badge,
    _render_debug_page,
    _render_frames,
    _render_kv,
)


class TestH:
    def test_plain(self) -> None:
        assert _h("p", "hello") == "<p>hello</p>"

    def test_attr_value(self) -> None:
        assert _h("a", "x", href="/link") == '<a href="/link">x</a>'  # noqa: Q000

    def test_attr_true_is_bare(self) -> None:
        assert _h("input", type_="text", disabled=True) == '<input type="text" disabled></input>'

    def test_attr_none_and_false_omitted(self) -> None:
        assert _h("div", "x", id_=None, hidden=False) == "<div>x</div>"

    def test_underscore_to_hyphen(self) -> None:
        assert _h("div", "x", x_data="y") == '<div x-data="y">x</div>'

    def test_trailing_underscore_stripped(self) -> None:
        assert _h("div", "x", class_="c") == '<div class="c">x</div>'

    def test_attr_values_escaped(self) -> None:
        assert _h("div", "x", title='a"b&c') == '<div title="a&quot;b&amp;c">x</div>'  # noqa: Q000

    def test_dict_children_contribute_attrs(self) -> None:
        assert _h("div", "x", {"class": "c", "hidden": None, "flag": True}) == (
            '<div class="c" flag>x</div>'
        )

    def test_none_children_skipped(self) -> None:
        assert _h("div", None, "x", None) == "<div>x</div>"

    def test_multiple_text_children(self) -> None:
        assert _h("p", "a", "b") == "<p>ab</p>"

    def test_no_children(self) -> None:
        assert _h("br") == "<br></br>"

    def test_non_string_attr_value(self) -> None:
        assert _h("div", "x", data_count=3) == '<div data-count="3">x</div>'


class TestMethodBadge:
    def test_known_methods(self) -> None:
        assert _method_badge("GET") == '<span class="badge badge-get">GET</span>'
        assert _method_badge("post") == '<span class="badge badge-post">POST</span>'
        assert _method_badge("DELETE") == '<span class="badge badge-delete">DELETE</span>'

    def test_unknown_method(self) -> None:
        assert _method_badge("TEAPOT") == '<span class="badge badge-other">TEAPOT</span>'

    def test_method_escaped(self) -> None:
        out = _method_badge("<script>")
        assert "<script>" not in out
        assert "badge-other" in out


class TestRenderFrames:
    def _frame(self, **kw) -> dict:
        base: dict = {
            "name": "handler",
            "filename": "/app/views.py",
            "lineno": 12,
            "lines": [
                (11, "def handler():", False),
                (12, "raise ValueError('boom')", True),
                (13, "pass", False),
            ],
        }
        base.update(kw)
        return base

    def test_empty_frames_placeholder(self) -> None:
        out = _render_frames([])
        assert "No traceback available." in out

    def test_single_frame_renders(self) -> None:
        out = _render_frames([self._frame()])
        assert '<span class="fn-name">handler</span>' in out
        assert "/app/views.py:12" in out
        assert "error-line" in out
        assert "top-frame" in out
        assert "raise ValueError(&#x27;boom&#x27;)" in out or "raise ValueError" in out

    def test_multiple_frames_top_highlighted(self) -> None:
        bottom = self._frame(name="root")
        top = self._frame(name="leaf")
        out = _render_frames([bottom, top])
        # last frame gets the top-frame class; first does not
        first_div = out.split("</div>\n")[0]
        assert "top-frame" not in first_div
        assert "top-frame" in out

    def test_special_chars_escaped(self) -> None:
        frame = self._frame(name="a<b>&", filename='/x/y"z.py')
        out = _render_frames([frame])
        assert "a<b>&" not in out
        assert "a&lt;b&gt;&amp;" in out


class TestRenderKv:
    def test_empty_placeholder(self) -> None:
        assert _render_kv([]) == '<p style="color:#64748b;font-size:.9rem;">None</p>'

    def test_pairs(self) -> None:
        out = _render_kv([("method", "GET"), ("path", "/a/b")])
        assert 'class="kv-table"' in out
        assert "<td>method</td>" in out
        assert "<td>GET</td>" in out
        assert "<td>/a/b</td>" in out

    def test_values_escaped(self) -> None:
        out = _render_kv([("q", "<script>")])
        assert "<script>" not in out
        assert "&lt;script&gt;" in out

    def test_non_string_values(self) -> None:
        out = _render_kv([("status", 404), ("body", None)])
        assert "<td>404</td>" in out
        assert "<td>None</td>" in out


class TestRenderDebugPage:
    def test_full_page(self) -> None:
        page = _render_debug_page(
            headline="Internal Server Error",
            exc_type="ValueError",
            exc_msg="bad value",
            chain_html="",
            traceback_html="<p>tb</p>",
            request_html="<p>req</p>",
            query_html="<p>q</p>",
            python_ver="3.11",
            lx_ver="0.1.0",
        )
        assert page.startswith("<!DOCTYPE html>")
        assert '<html lang="en">' in page
        assert "<title>Internal Server Error</title>" in page
        assert "Quadkit — Debug Mode" in page
        assert "ValueError: bad value" in page
        assert "Traceback (most recent call last)" in page
        assert "Request" in page
        assert "Query Parameters" in page
        assert "Python 3.11" in page
        assert "Quadkit 0.1.0" in page
        assert "debug mode" in page
        assert page.rstrip().endswith("</html>")

    def test_headline_escaped_in_title(self) -> None:
        page = _render_debug_page(
            headline="<b>err</b>",
            exc_type="E",
            exc_msg="m",
            chain_html="",
            traceback_html="",
            request_html="",
            query_html="",
            python_ver="3.11",
            lx_ver="0.1.0",
        )
        assert "<title><b>err</b></title>" not in page
        assert "<title>&lt;b&gt;err&lt;/b&gt;</title>" in page

    def test_exception_message_included(self) -> None:
        page = _render_debug_page(
            headline="E",
            exc_type="ValueError",
            exc_msg="bad value",
            chain_html="",
            traceback_html="",
            request_html="",
            query_html="",
            python_ver="3.11",
            lx_ver="0.1.0",
        )
        assert 'class="exc-type"' in page
        assert "ValueError: bad value" in page

    def test_headline_escaped_in_body(self) -> None:
        page = _render_debug_page(
            headline='<h1 x="1">',
            exc_type="E",
            exc_msg="m",
            chain_html="",
            traceback_html="",
            request_html="",
            query_html="",
            python_ver="3.11",
            lx_ver="0.1.0",
        )
        assert '<h1 x="1">' not in page
        assert "&lt;h1 x=&quot;1&quot;&gt;" in page
