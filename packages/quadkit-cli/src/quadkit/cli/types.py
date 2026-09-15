"""Type definitions for quadkit CLI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandType(str, Enum):
    """Type of CLI command."""

    INIT = "init"
    RUN = "run"
    BUILD = "build"
    GENERATE = "generate"


@dataclass
class CLIResult:
    """Result of a CLI command execution."""

    success: bool
    message: str = ""
    data: dict[str, object] | None = None


__all__ = [
    "CLIResult",
    "CommandType",
]
