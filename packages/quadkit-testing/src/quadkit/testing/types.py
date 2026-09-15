"""Type aliases and enums for quadkit-testing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

__all__ = [
    "OverrideDict",
    "ServiceEndpoint",
    "SnapshotName",
    "SnapshotValue",
    "TestFactory",
]

TestFactory: TypeAlias = Callable[[], Any] | str
"""Factory for creating an Application — either a callable or dotted import string."""

OverrideDict: TypeAlias = dict[type, Any]
"""Mapping of service types to replacement instances for DI overrides."""

ServiceEndpoint: TypeAlias = tuple[str, int]
"""(hostname, port) tuple for service availability checks."""

SnapshotName: TypeAlias = str
"""Unique identifier for a snapshot — used as filename stem."""

SnapshotValue: TypeAlias = Any
"""JSON-serializable value for snapshot comparison."""
