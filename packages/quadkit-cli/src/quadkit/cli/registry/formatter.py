"""Formatter registry for output formatting.

This module provides a registry pattern for output formatters (JSON, YAML, table, etc).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit import serialization as json


@dataclass
class FormatOptions:
    """Options for formatting."""

    indent: int = 2
    sort_keys: bool = False
    color: bool = True


class OutputFormatter(abc.ABC):
    """Abstract base class for output formatters."""

    name: ClassVar[str]
    content_type: ClassVar[str]
    file_extension: ClassVar[str]

    @abc.abstractmethod
    def format(self, data: Any, options: FormatOptions | None = None) -> str:
        """Format data for output."""

    @abc.abstractmethod
    def parse(self, input_str: str) -> Any:
        """Parse input string into data."""


class JSONFormatter(OutputFormatter):
    """JSON output formatter."""

    name = "json"
    content_type = "application/json"
    file_extension = "json"

    def format(self, data: Any, options: FormatOptions | None = None) -> str:
        opts = options or FormatOptions()
        return json.dumps(
            data,
            indent=opts.indent,
            sort_keys=opts.sort_keys,
            default=str,
        ).decode("utf-8")

    def parse(self, input_str: str) -> Any:
        return json.loads(input_str)


class YAMLFormatter(OutputFormatter):
    """YAML output formatter."""

    name = "yaml"
    content_type = "application/x-yaml"
    file_extension = "yaml"

    def format(self, data: Any, options: FormatOptions | None = None) -> str:
        try:
            import yaml

            return yaml.dump(data, sort_keys=False, default_flow_style=False)
        except ImportError:
            return json.dumps(data, indent=2, default=str).decode("utf-8")

    def parse(self, input_str: str) -> Any:
        try:
            import yaml

            return yaml.safe_load(input_str)
        except ImportError:
            raise ValueError("PyYAML not installed") from None


class TableFormatter(OutputFormatter):
    """Table output formatter for terminal."""

    name = "table"
    content_type = "text/plain"
    file_extension = "txt"

    def format(self, data: Any, options: FormatOptions | None = None) -> str:
        if not isinstance(data, list) or not data:
            return str(data)

        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = [[row.get(h, "") for h in headers] for row in data]
            return self._format_table(headers, rows)
        if isinstance(data[0], (list, tuple)):
            return self._format_table([], data)

        return str(data)

    def _format_table(self, headers: list, rows: list) -> str:
        if not rows:
            return ""

        col_widths = []
        if headers:
            for _i, h in enumerate(headers):
                col_widths.append(len(str(h)))
        else:
            for row in rows:
                for i, cell in enumerate(row):
                    if i >= len(col_widths):
                        col_widths.append(0)
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        lines = []
        if headers:
            header_line = " | ".join(
                str(h).ljust(col_widths[i]) for i, h in enumerate(headers)
            )
            lines.append(header_line)
            lines.append("-" * len(header_line))

        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
            )
            lines.append(row_line)

        return "\n".join(lines)

    def parse(self, input_str: str) -> Any:
        raise NotImplementedError("Table parsing not supported")


class SimpleFormatter(OutputFormatter):
    """Simple key=value output formatter."""

    name = "simple"
    content_type = "text/plain"
    file_extension = "txt"

    def format(self, data: Any, options: FormatOptions | None = None) -> str:
        if isinstance(data, dict):
            lines = []
            for key, value in data.items():
                lines.append(f"{key}: {value}")
            return "\n".join(lines)
        if isinstance(data, list):
            return "\n".join(str(item) for item in data)
        return str(data)

    def parse(self, input_str: str) -> Any:
        result = {}
        for line in input_str.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result


class FormatterRegistry:
    """Registry for output formatters.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin formatters.
    """

    def __init__(self) -> None:
        self._formatters: dict[str, OutputFormatter] = {}

    def register(self, formatter: type[OutputFormatter]) -> None:
        """Register a formatter class."""
        instance = formatter()
        self._formatters[formatter.name] = instance

    def get(self, name: str) -> OutputFormatter | None:
        """Get a formatter by name."""
        return self._formatters.get(name)

    def get_all(self) -> dict[str, OutputFormatter]:
        """Get all registered formatters."""
        return self._formatters.copy()

    def get_choices(self) -> list[str]:
        """Get list of available formatter names."""
        return list(self._formatters.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[OutputFormatter], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            JSONFormatter,
            YAMLFormatter,
            TableFormatter,
            SimpleFormatter,
        )

    @classmethod
    def with_defaults(cls) -> FormatterRegistry:
        """Return an instance populated with the built-in formatters."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def format_output(
    data: Any,
    format_name: str = "json",
    options: FormatOptions | None = None,
) -> str:
    """Format data using the specified formatter."""
    registry = FormatterRegistry.with_defaults()
    formatter = registry.get(format_name)
    if not formatter:
        raise ValueError(f"Unknown format: {format_name}")
    return formatter.format(data, options)


__all__ = [
    "FormatOptions",
    "FormatterRegistry",
    "JSONFormatter",
    "OutputFormatter",
    "SimpleFormatter",
    "TableFormatter",
    "YAMLFormatter",
    "format_output",
]
