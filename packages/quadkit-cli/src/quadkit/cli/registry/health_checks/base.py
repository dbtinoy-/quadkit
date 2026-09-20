"""Shared base types for CLI health checks."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    """Status of a health check."""

    PASS = "pass"  # noqa: S105  # health check status, not a credential
    WARNING = "warning"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class CheckResult:
    """Result of a health check."""

    name: str
    status: CheckStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def icon(self) -> str:
        """Get icon for status."""
        return {
            CheckStatus.PASS: "✓",
            CheckStatus.WARNING: "⚠",
            CheckStatus.FAIL: "✗",
            CheckStatus.SKIP: "○",
        }.get(self.status, "?")

    @property
    def color(self) -> str:
        """Get color for status."""
        return {
            CheckStatus.PASS: "success",
            CheckStatus.WARNING: "warning",
            CheckStatus.FAIL: "error",
            CheckStatus.SKIP: "dim",
        }.get(self.status, "")


class HealthCheck(abc.ABC):
    """Abstract base class for health checks."""

    @abc.abstractmethod
    def check(self) -> CheckResult:
        """Run the health check and return the result."""

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of this check."""

    def get_category(self) -> str:
        """Get the category for this check (for grouping)."""
        return "General"


__all__ = ["CheckResult", "CheckStatus", "HealthCheck"]
