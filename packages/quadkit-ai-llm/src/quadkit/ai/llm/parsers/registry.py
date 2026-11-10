"""Parser Registry for managing output parsers."""

from __future__ import annotations

from typing import Any

from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class ParserRegistry:
    """Registry for managing output parsers by name.

    Provides a central registry for looking up parsers by name,
    similar to LangChain's parser registry.

    Example:
        >>> registry = ParserRegistry()
        >>> registry.register("json", JSONOutputParser())
        >>> parser = registry.get("json")
        >>> assert parser is not None
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._parsers: dict[str, Any] = {}

    def register(self, name: str, parser: Any) -> None:
        """Register a parser with a name.

        Args:
            name: Unique name for the parser.
            parser: Parser instance to register.
        """
        self._parsers[name] = parser
        logger.debug("parser_registered", name=name)

    def get(self, name: str) -> Any:
        """Get a parser by name.

        Args:
            name: Name of the parser to retrieve.

        Returns:
            The registered parser.

        Raises:
            KeyError: If no parser is registered with that name.
        """
        if name not in self._parsers:
            available = list(self._parsers.keys())
            raise KeyError(
                f"No parser registered with name {name!r}. Available: {available}"
            )
        return self._parsers[name]

    def get_or_none(self, name: str) -> Any | None:
        """Get a parser by name, returning None if not found.

        Args:
            name: Name of the parser to retrieve.

        Returns:
            The registered parser, or None if not found.
        """
        return self._parsers.get(name)

    def list_parsers(self) -> list[str]:
        """List all registered parser names.

        Returns:
            List of registered parser names.
        """
        return list(self._parsers.keys())

    def unregister(self, name: str) -> None:
        """Unregister a parser by name.

        Args:
            name: Name of the parser to unregister.

        Raises:
            KeyError: If no parser is registered with that name.
        """
        if name not in self._parsers:
            raise KeyError(f"No parser registered with name {name!r}")
        del self._parsers[name]
        logger.debug("parser_unregistered", name=name)

    @classmethod
    def _default_entries(cls) -> dict[str, Any]:
        """Declare the built-in output parsers."""
        from quadkit.ai.llm.parsers.csv import CSVOutputParser
        from quadkit.ai.llm.parsers.enum import EnumOutputParser
        from quadkit.ai.llm.parsers.json import JSONOutputParser
        from quadkit.ai.llm.parsers.pydantic import PydanticOutputParser

        return {
            "json": JSONOutputParser(),
            "pydantic": PydanticOutputParser,
            "enum": EnumOutputParser,
            "csv": CSVOutputParser(),
        }

    @classmethod
    def with_defaults(cls) -> ParserRegistry:
        """Create a registry with default parsers pre-registered."""
        registry = cls()
        for name, parser in cls._default_entries().items():
            registry.register(name, parser)
        return registry


__all__ = ["ParserRegistry"]
