"""Value parser classes for authorization service."""

from __future__ import annotations

from collections.abc import Sequence
import threading
from typing import Any, Protocol, cast

from quadkit import serialization as json


class ValueParser(Protocol):
    """Protocol for value parsers."""

    def can_parse(self, val: Any) -> bool:
        """Check if this parser can handle the given value."""
        ...

    def parse(self, val: Any) -> list[str]:
        """Parse the value into a list of strings."""
        ...


class StringValueParser:
    """Parser for string values, including JSON-encoded lists."""

    def can_parse(self, val: Any) -> bool:
        return isinstance(val, str)

    def parse(self, val: Any) -> list[str]:
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except (ValueError, TypeError, json.JSONDecodeError):
            return [val]


class ListValueParser:
    """Parser for sequence values (list, tuple, set, frozenset).

    A principal's ``roles`` is often a tuple — frozen dataclasses, Pydantic
    tuple fields, ``("admin",)`` written by hand — and the parser used to
    require ``list`` exactly. Nothing matched a tuple, so the registry's
    ``str()`` fallback swallowed the whole thing and produced one bogus role
    name (``("demo_role",)`` → ``'(\'demo_role\',)'``), which failed every
    role check while the 403 blamed the user for lacking a role they held.
    Widening here keeps the fallback a last resort rather than a silent
    absorber of sequence types.
    """

    def can_parse(self, val: Any) -> bool:
        return isinstance(val, (list, tuple, set, frozenset))

    def parse(self, val: Any) -> list[str]:
        # A tuple/set is not a list: materialise it, and keep the element
        # order for the list/tuple cases (sets are unordered by nature).
        return list(cast("Sequence[str]", val))


class NoneValueParser:
    """Parser for None values."""

    def can_parse(self, val: Any) -> bool:
        return val is None

    def parse(self, val: Any) -> list[str]:
        return []


class ValueParserRegistry:
    """Registry for value parsers.

    Provides extensible parsing of various value types into string lists.
    Thread-safe registry for value parsers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._parsers: list[ValueParser] = []
        self._register_default_parsers()

    def _register_default_parsers(self) -> None:
        """Register the default value parsers."""
        self._parsers = [
            StringValueParser(),
            ListValueParser(),
            NoneValueParser(),
        ]

    def register_parser(self, parser: ValueParser) -> None:
        """Register a custom value parser."""
        with self._lock:
            self._parsers.insert(0, parser)

    def parse(self, val: Any) -> list[str]:
        """Parse the value using registered parsers."""
        with self._lock:
            for parser in self._parsers:
                if parser.can_parse(val):
                    return parser.parse(val)
            return [str(val)]


# Global registry instance
_value_parser_registry = ValueParserRegistry()

__all__ = [
    "ListValueParser",
    "NoneValueParser",
    "StringValueParser",
    "ValueParser",
    "ValueParserRegistry",
]
