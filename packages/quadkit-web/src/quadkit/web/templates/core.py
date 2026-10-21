"""Template rendering core implementation (migrated from legacy module).

This module provides `Jinja2Templates`, `TemplateResponse`, `render_template`,
and `template_response` as the canonical implementations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from markupsafe import Markup

from quadkit import serialization as json
from quadkit.logging import get_logger
from quadkit.primitives.trusted_html import TrustedHTML, json_for_html
from quadkit.web.transport.responses import HTMLResponse

logger = get_logger(__name__)

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    Environment = None  # type: ignore[assignment, misc]
    FileSystemLoader = None  # type: ignore[assignment, misc]
    select_autoescape = None  # type: ignore[assignment]


class Jinja2Templates:
    """Jinja2-powered template engine with constructor injection support.

    Designed for full DI compliance: all configuration is passed through the
    constructor so the engine can be registered as a container singleton and
    injected into controllers or request handlers.

    Example::

        # Provider registration
        templates = Jinja2Templates(
            directory="templates",
            context_processors=[add_request_context],
        )
        container.singleton(Jinja2Templates, lambda: templates)

        # Controller usage
        class MyController:
            def __init__(self, templates: Jinja2Templates) -> None:
                self._templates = templates

            @get("/")
            async def index(self) -> HTMLResponse:
                return self._templates.render_response("index.html", {"title": "Home"})

    Args:
        directory: Path to the Jinja2 templates directory.  Defaults to
            ``"templates"`` relative to the working directory.
        context_processors: Optional list of callables that receive the
            context dict and may add/transform keys before rendering.
        **env_kwargs: Extra keyword arguments forwarded to the underlying
            :class:`jinja2.Environment` constructor.
    """

    def __init__(
        self,
        directory: str | Path = "templates",
        context_processors: list | None = None,
        **env_kwargs: Any,
    ):
        if Environment is None:
            raise ImportError(
                "Jinja2 is required to use templates. Install it with 'pip install jinja2' "
                "or avoid importing template helpers when Jinja2 is not available.",
            )

        self.directory = Path(directory)
        self.context_processors = context_processors or []

        default_env_kwargs: dict[str, Any] = {
            "loader": FileSystemLoader(str(self.directory)),
            "autoescape": select_autoescape(["html", "xml"]),
            "trim_blocks": True,
            "lstrip_blocks": True,
        }
        default_env_kwargs.update(env_kwargs)

        self.env = Environment(**default_env_kwargs)

        self._add_default_filters()
        self._add_default_globals()

    def _add_default_filters(self) -> None:
        def tojson(obj: Any) -> TrustedHTML | Markup:
            """Serialize ``obj`` to JSON that is safe to embed in HTML.

            Delegates to :func:`quadkit.primitives.trusted_html.json_for_html`,
            which escapes the HTML/JS-significant characters and grants trust
            as a single step. JSON is *not* safe to embed verbatim: a value
            such as ``</script><img src=x onerror=…>`` is valid JSON and would
            otherwise close the surrounding script element.
            """
            try:
                return json_for_html(
                    obj,
                    source="quadkit.web tojson filter",
                    dumps=lambda value: json.dumps_str(
                        value, default=str, ensure_ascii=False
                    ),
                )
            except (TypeError, ValueError) as e:
                logger.debug("tojson filter failed, falling back to str(): %s", e)
                # Not marked safe: autoescape must still escape this.
                return Markup.escape(str(obj))

        def format_datetime(value: Any, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
            if value is None:
                return ""
            if isinstance(value, (int, float)):
                try:
                    return datetime.fromtimestamp(value).strftime(fmt)
                except (ValueError, OSError, TypeError) as e:
                    logger.debug("format_datetime timestamp conversion failed: %s", e)
                    return str(value)
            try:
                return cast("str", value.strftime(fmt))
            except (AttributeError, TypeError) as e:
                logger.debug("format_datetime failed to format value: %s", e)
                return str(value)

        self.env.filters["tojson"] = tojson
        self.env.filters["format_datetime"] = format_datetime

    def _add_default_globals(self) -> None:
        self.env.globals["now"] = lambda: datetime.now(UTC)
        self.env.globals["static_url"] = lambda path: f"/static/{str(path).lstrip('/')}"

    def get_template(self, name: str) -> Any:
        return self.env.get_template(name)

    def render_template(
        self,
        name: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template to a string.

        Args:
            name: Template file name relative to the templates directory.
            context: Base context mapping passed to the template.
            **kwargs: Additional context variables merged over *context*.

        Returns:
            Rendered HTML string.
        """
        template = self.get_template(name)
        context = context or {}
        context.update(kwargs)

        for processor in self.context_processors:
            context = processor(context)

        return cast("str", template.render(**context))

    def render_response(
        self,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HTMLResponse:
        """Render a template and return an :class:`~quadkit.web.transport.responses.HTMLResponse`.

        Args:
            name: Template file name relative to the templates directory.
            context: Base context mapping passed to the template.
            status_code: HTTP status code for the response.  Defaults to 200.
            headers: Optional extra HTTP response headers.
            **kwargs: Additional context variables merged over *context*.

        Returns:
            An :class:`~quadkit.web.transport.responses.HTMLResponse` with the rendered content.
        """
        content = self.render_template(name, context, **kwargs)
        return HTMLResponse(content=content, status_code=status_code, headers=headers)


class TemplateResponse(HTMLResponse):
    """Template-based HTML response"""

    def __init__(
        self,
        template: Jinja2Templates,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        content = template.render_template(name, context, **kwargs)
        super().__init__(content=content, status_code=status_code, headers=headers)


def render_template(
    name: str,
    context: dict[str, Any] | None = None,
    templates: Jinja2Templates | None = None,
    **kwargs: Any,
) -> str:
    if templates is None:
        templates = Jinja2Templates()
    return templates.render_template(name, context, **kwargs)


def template_response(
    name: str,
    context: dict[str, Any] | None = None,
    templates: Jinja2Templates | None = None,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    **kwargs: Any,
) -> TemplateResponse:
    if templates is None:
        templates = Jinja2Templates()
    return TemplateResponse(templates, name, context, status_code, headers, **kwargs)
