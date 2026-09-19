"""Protocols for the config subsystem.

Defines ``ConfigSourceProtocol`` for pluggable configuration source
implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from quadkit.config.types import ConfigSourceType


class ConfigSourceProtocol(Protocol):
    """Protocol for pluggable configuration sources."""

    def load(self) -> dict[str, Any]:
        """Load and return configuration values as a plain dict."""
        ...

    @property
    def source_type(self) -> ConfigSourceType:
        """Return the type of this configuration source."""
        ...


__all__ = ["ConfigSourceProtocol"]
