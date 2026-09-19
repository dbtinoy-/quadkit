"""Type definitions for the config subsystem.

Provides the ``ConfigSourceType`` enum that identifies
how a configuration value was loaded.
"""

from __future__ import annotations

from enum import StrEnum


class ConfigSourceType(StrEnum):
    """Enum of configuration source types."""

    FILE = "file"
    ENVIRONMENT = "environment"
    CLI = "cli"
    DIRECTORY = "directory"
    MEMORY = "memory"


__all__ = ["ConfigSourceType"]
