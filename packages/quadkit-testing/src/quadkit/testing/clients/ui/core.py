"""UI testing helpers for quadkit-ui components.

Provides ``render_component()`` and ``assert_html_contains()`` — lightweight
utilities for snapshot-style component tests.

Usage::

    from quadkit.testing.ui import render_component, assert_html_contains
    from myapp.ui.components import UserBadge

    def test_user_badge_renders_name():
        html = render_component(UserBadge, username="alice")
        assert_html_contains(html, tag="span", text="alice")
"""

from __future__ import annotations

import re
from typing import Any


def render_component(component_class: type, *args: Any, **kwargs: Any) -> str:
    """Instantiate *component_class* and return its rendered HTML string.

    Args:
        component_class: A :class:`~quadkit.ui.base.Component` subclass.
        *args: Positional arguments forwarded to the component constructor.
        **kwargs: Keyword arguments forwarded to the component constructor.

    Returns:
        HTML string produced by ``component_class(*args, **kwargs).__html__()``.
    """
    from quadkit.ui.core.base import NoContext, render_to_string

    with NoContext():
        component = component_class(*args, **kwargs)
    return render_to_string(component)


def assert_html_contains(
    html: str,
    *,
    tag: str | None = None,
    text: str | None = None,
    attr: str | None = None,
    attr_value: str | None = None,
    css_class: str | None = None,
) -> None:
    """Assert that *html* contains expected content.

    At least one of *tag*, *text*, *attr*, or *css_class* must be provided.

    Args:
        html: The HTML string to search.
        tag: If provided, assert an element with this tag name is present
            (e.g. ``"button"``, ``"span"``).
        text: If provided, assert this text substring is present in *html*.
        attr: If provided, assert this attribute name is present in *html*
            (e.g. ``"hx-post"``, ``"disabled"``).
        attr_value: If provided (alongside *attr*), assert the attribute
            has exactly this value.
        css_class: If provided, assert this CSS class appears in a ``class``
            attribute value.

    Raises:
        AssertionError: If any of the specified conditions are not met.

    Example::

        assert_html_contains(html, tag="button", css_class="btn-primary")
        assert_html_contains(html, attr="hx-post", attr_value="/submit")
        assert_html_contains(html, text="Hello, Alice")
    """
    if tag is not None:
        pattern = rf"<{re.escape(tag)}[\s>/]"
        assert re.search(pattern, html, re.IGNORECASE), (
            f"Expected <{tag}> element in HTML, not found.\nHTML:\n{html}"
        )

    if text is not None:
        assert text in html, (
            f"Expected text {text!r} in HTML, not found.\nHTML:\n{html}"
        )

    if attr is not None:
        escaped_attr = re.escape(attr)
        if attr_value is not None:
            pattern = rf'{escaped_attr}="{re.escape(attr_value)}"'
            assert re.search(pattern, html), (
                f"Expected attribute {attr!r}={attr_value!r} in HTML, not found.\n"
                f"HTML:\n{html}"
            )
        else:
            assert attr in html, (
                f"Expected attribute {attr!r} in HTML, not found.\nHTML:\n{html}"
            )

    if css_class is not None:
        # Match class="..." containing the target class token
        pattern = rf'class="[^"]*\b{re.escape(css_class)}\b[^"]*"'
        assert re.search(pattern, html), (
            f"Expected CSS class {css_class!r} in HTML, not found.\nHTML:\n{html}"
        )


__all__ = ["assert_html_contains", "render_component"]
