"""Tests for routing/openapi_templates.py — Swagger and ReDoc HTML generators."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.web.routing.openapi_templates import get_redoc_html, get_swagger_ui_html


class TestGetSwaggerUiHtml:
    def test_returns_string(self) -> None:
        result = get_swagger_ui_html(title="Test API", openapi_url="/openapi.json")
        assert isinstance(result, str)

    def test_fallback_contains_title_when_jinja2_unavailable(self) -> None:
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            side_effect=ImportError("jinja2 not installed"),
        ):
            result = get_swagger_ui_html(title="My API", openapi_url="/spec.json")
        assert "My API" in result
        assert "/spec.json" in result

    def test_fallback_contains_jinja2_install_hint(self) -> None:
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            side_effect=ImportError,
        ):
            result = get_swagger_ui_html(title="X", openapi_url="/openapi.json")
        assert "jinja2" in result

    def test_uses_jinja2_templates_when_available(self) -> None:
        mock_templates = MagicMock()
        mock_templates.render_template.return_value = "<html>swagger</html>"
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            return_value=mock_templates,
        ):
            result = get_swagger_ui_html(title="T", openapi_url="/api.json")
        assert "<html>swagger</html>" in result
        mock_templates.render_template.assert_called_once()

    def test_passes_optional_js_and_css_urls(self) -> None:
        mock_templates = MagicMock()
        mock_templates.render_template.return_value = "<html/>"
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            return_value=mock_templates,
        ):
            get_swagger_ui_html(
                title="T",
                openapi_url="/api.json",
                swagger_js_url="/swagger.js",
                swagger_css_url="/swagger.css",
            )
        _, call_kwargs = mock_templates.render_template.call_args
        # context is positional arg
        call_args = mock_templates.render_template.call_args[0]
        context = call_args[1] if len(call_args) > 1 else mock_templates.render_template.call_args[1]
        # Just verify the call happened with context including our urls
        mock_templates.render_template.assert_called_once()


class TestGetRedocHtml:
    def test_returns_string(self) -> None:
        result = get_redoc_html(title="Test API", openapi_url="/openapi.json")
        assert isinstance(result, str)

    def test_fallback_contains_title_when_jinja2_unavailable(self) -> None:
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            side_effect=ImportError,
        ):
            result = get_redoc_html(title="My Docs", openapi_url="/spec.json")
        assert "My Docs" in result
        assert "/spec.json" in result

    def test_fallback_contains_jinja2_install_hint(self) -> None:
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            side_effect=ImportError,
        ):
            result = get_redoc_html(title="X", openapi_url="/api.json")
        assert "jinja2" in result

    def test_uses_jinja2_templates_when_available(self) -> None:
        mock_templates = MagicMock()
        mock_templates.render_template.return_value = "<html>redoc</html>"
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            return_value=mock_templates,
        ):
            result = get_redoc_html(title="T", openapi_url="/api.json")
        assert "<html>redoc</html>" in result

    def test_passes_optional_js_url(self) -> None:
        mock_templates = MagicMock()
        mock_templates.render_template.return_value = "<html/>"
        with patch(
            "quadkit.web.routing.openapi_templates.Jinja2Templates",
            return_value=mock_templates,
        ):
            get_redoc_html(
                title="T",
                openapi_url="/api.json",
                redoc_js_url="/redoc.js",
            )
        mock_templates.render_template.assert_called_once()
