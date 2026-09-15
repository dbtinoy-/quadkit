"""Templates package - canonical exports"""
from __future__ import annotations

from quadkit.web.templates.core import (
    Jinja2Templates,
    TemplateResponse,
    render_template,
    template_response,
)

__all__ = [
    "Jinja2Templates",
    "TemplateResponse",
    "render_template",
    "template_response",
]
