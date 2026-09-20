"""Round 41 hardening pins — quadkit-web: docs UI falls back on any error.

get_swagger_ui_html — when template rendering fails with a non-Import
error type (e.g. a broken template environment), the docs endpoint
returns the plain-HTML fallback, never a raw raise (the API docs page
must not 500).

Run with: pytest tests/unit/test_round41_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quadkit.web.routing import openapi_templates as module


class _DriverError(Exception):
    """Stand-in for a template-engine failure (not ImportError)."""


class TestSwaggerUiHtml:
    def test_render_failure_falls_back_to_plain_html(self) -> None:
        def _broken_templates(*_args, **_kwargs):
            raise _DriverError("template engine wedged")

        with patch.object(module, "Jinja2Templates", _broken_templates):
            html = module.get_swagger_ui_html("My API", "/api/openapi.json")

        assert "<h1>My API</h1>" in html
        assert "OpenAPI JSON" in html
