from datetime import datetime
import pytest

pytest.importorskip("jinja2")

from quadkit.web.templates import Jinja2Templates


def test_template_filters_and_globals(tmp_path):
    # Create template directory and file
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    tpl_file = tpl_dir / "test.html"
    tpl_file.write_text(
        "json: {{ data|tojson }}\n"
        "time: {{ value|format_datetime }}\n"
        "now: {{ now() }}\n"
        "static: {{ static_url('img.png') }}\n",
    )

    templates = Jinja2Templates(directory=tpl_dir)

    content = templates.render_template(
        "test.html",
        {"data": {"a": 1}, "value": datetime(2020, 1, 1, 12, 0)},
    )

    assert "json:" in content
    assert '"a"' in content or '"a"' in content
    assert "time:" in content
    assert "2020" in content
    assert "now:" in content
    assert "static: /static/img.png" in content


def test_tojson_escapes_html_delimiters(tmp_path):
    """`tojson` must not let JSON string data break out of a <script> block.

    JSON is not "safe by construction": `</script>` is a valid JSON string
    payload, so emitting it verbatim inside a script element ends the element
    and lets the remainder be parsed as markup.
    """
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    (tpl_dir / "xss.html").write_text("<script>window.S = {{ data|tojson }};</script>")

    templates = Jinja2Templates(directory=tpl_dir)
    payload = "</script><img src=x onerror=alert(1)>"
    content = templates.render_template("xss.html", {"data": {"name": payload}})

    assert "</script><img" not in content
    assert "\\u003c" in content

    # The escaping must be lossless: it is a JSON \uXXXX escape, not a
    # mangling of the value.
    import json as stdjson
    import re

    match = re.search(r"window\.S = (.*);</script>", content)
    assert match is not None
    assert stdjson.loads(match.group(1))["name"] == payload


def test_tojson_escapes_js_line_separators(tmp_path):
    """U+2028/U+2029 are legal in JSON strings but terminate JS lines."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()
    (tpl_dir / "sep.html").write_text("<script>window.S = {{ data|tojson }};</script>")

    templates = Jinja2Templates(directory=tpl_dir)
    content = templates.render_template("sep.html", {"data": {"a": "x\u2028y\u2029z"}})

    assert "\u2028" not in content
    assert "\u2029" not in content
    assert "\\u2028" in content
    assert "\\u2029" in content
