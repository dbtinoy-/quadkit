"""Explicit capability type for already-sanitized or framework-owned HTML.

``TrustedHTML`` is the only final-state arbitrary verbatim string type in
Quadkit. It subclasses ``str`` so template engines (Jinja) and response
adapters treat it as a safe string through ``__html__``, exactly like the
legacy ``markupsafe.Markup`` did — but with mandatory attributable ownership
and no silent import.

``source`` identifies the sanitizer, template, or owned static producer
responsible for the value. It is audit metadata, not sanitization: callers
must never grant trust directly to unvalidated user input.

This module lives in ``quadkit.primitives`` rather than in a UI package
because the render-trust boundary is foundational: every package that emits
HTML needs it, and duplicating the capability type would let two
implementations of a security boundary drift apart.

Choosing a helper
-----------------

Prefer, in order:

1. :func:`json_for_html` — embedding data in a ``<script>`` block. Escapes
   and grants trust in one step, so the call site cannot get it wrong.
2. :func:`trusted_template_output` — output of an autoescaping template
   engine.
3. :func:`trusted_svg_icon` / :func:`trusted_static_script` — framework-owned
   static assets.
4. :func:`trusted_html` — the unrestricted grant. Every use is a standing
   assertion that the value cannot contain attacker-controlled markup.

The lower you go, the more you are asserting by hand. ``trusted_html`` is
audited by ``dev/checks/ui_trusted_html.py``.

.. warning::

   Granting trust is not sanitization. ``TrustedHTML`` records *who* vouched
   for a value; it cannot check *whether they were right*. A grant whose
   stated justification is false is still a vulnerability — see
   :func:`json_for_html` for the canonical example.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Callable


class TrustedHTML(str):
    """An escape-safe string with mandatory attributable ownership.

    Immutable: attempts to replace ``source`` (or normal ``str`` mutation
    paths) raise :class:`FrozenInstanceError`, matching the dataclass
    semantics the capability had when it was introduced.
    """

    __slots__ = ("source",)

    #: Audit metadata identifying the sanitizer/owner; set once in __new__.
    source: str

    @property
    def value(self) -> str:
        """Return the trusted markup string (compatibility accessor)."""
        return str.__str__(self)

    def __new__(cls, value: str, source: str) -> Self:
        if not isinstance(value, str):
            raise TypeError("TrustedHTML value must be a string")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("TrustedHTML requires a non-empty source")
        instance = super().__new__(cls, value)
        object.__setattr__(instance, "source", source)
        return instance

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenInstanceError(
            f"cannot assign to field {name!r}: TrustedHTML is immutable"
        )

    def __html__(self) -> str:
        """Return the explicitly trusted markup verbatim (Jinja-safe)."""
        return str(self)

    def __str__(self) -> str:
        """Return the string value (``str`` subclass)."""
        return str.__str__(self)

    def __repr__(self) -> str:
        return f"TrustedHTML({str.__str__(self)!r}, source={self.source!r})"


def trusted_html(value: str, *, source: str) -> TrustedHTML:
    """Grant explicit verbatim-markup trust with attributable ownership."""
    return TrustedHTML(value=value, source=source)


def trusted_template_output(value: str, *, template: str) -> TrustedHTML:
    """Trust markup produced by a template engine at its output boundary.

    The caller must record the template's autoescape policy in the template
    name/owner so review can confirm user data cannot reach the output raw.
    """
    return TrustedHTML(value=value, source=f"template output ({template})")


#: Characters escaped before JSON is embedded in an HTML document.
#:
#: ``<`` and ``>`` stop a string value from closing the enclosing element
#: (the ``</script>`` breakout); ``&`` stops HTML-entity reinterpretation;
#: U+2028 and U+2029 are legal inside JSON strings but are line terminators
#: to JavaScript parsers, which breaks the surrounding statement.
#:
#: Every replacement is a JSON ``\uXXXX`` escape, so the text still parses
#: to exactly the same value — this is lossless, not a mangling.
_JSON_HTML_ESCAPES: tuple[tuple[str, str], ...] = (
    ("&", "\\u0026"),
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("\u2028", "\\u2028"),
    ("\u2029", "\\u2029"),
)


def escape_json_for_html(json_text: str) -> str:
    """Escape HTML/JS-significant characters in an already-serialized JSON string.

    Returns plain ``str``; it grants no trust. Use :func:`json_for_html`
    unless you are serializing separately and need the escaping alone.
    """
    for char, escaped in _JSON_HTML_ESCAPES:
        json_text = json_text.replace(char, escaped)
    return json_text


def json_for_html(
    value: Any,
    *,
    source: str,
    dumps: Callable[[Any], str],
) -> TrustedHTML:
    """Serialize ``value`` to JSON that is safe to embed in an HTML document.

    This is the supported way to pass server state to client-side scripts::

        <script>window.STATE = {{ data|tojson }};</script>

    JSON is **not** safe to embed verbatim. ``</script>`` is a valid JSON
    string value, so serializing attacker-controlled data straight into a
    script element lets the attacker close the element and inject markup::

        {"name": "</script><img src=x onerror=alert(1)>"}

    Escaping and trust-granting happen together here precisely so that a
    caller cannot serialize, forget to escape, and then mark the result
    trusted. Any code path that serializes JSON into HTML by hand and calls
    :func:`trusted_html` on the result is a bug.

    Args:
        value: Any JSON-serializable object.
        source: Audit metadata identifying the caller granting trust.
        dumps: Serializer to use, normally ``quadkit.serialization.dumps_str``.
            It is injected rather than imported because ``quadkit.primitives``
            is foundational and must not depend on ``quadkit.serialization``.

    Returns:
        A :class:`TrustedHTML` whose payload parses to ``value`` unchanged.
    """
    return TrustedHTML(
        value=escape_json_for_html(dumps(value)),
        source=f"JSON for HTML ({source})",
    )


def trusted_svg_icon(value: str, *, name: str) -> TrustedHTML:
    """Trust an owned, versioned SVG icon definition (framework assets only)."""
    return TrustedHTML(value=value, source=f"owned SVG icon ({name})")


def trusted_static_script(value: str, *, asset: str) -> TrustedHTML:
    """Trust a shipped static script rendered inline at a named boundary."""
    return TrustedHTML(value=value, source=f"static script ({asset})")


__all__ = [
    "TrustedHTML",
    "escape_json_for_html",
    "json_for_html",
    "trusted_html",
    "trusted_static_script",
    "trusted_svg_icon",
    "trusted_template_output",
]
