"""Type definitions for the core subsystem.

TypeVars and type aliases used across builders, registries, and contexts.
No business logic; pure parameterisation.
"""

from __future__ import annotations

from typing import TypeAlias, TypeVar

K = TypeVar("K")  # Registry key type
V = TypeVar("V")  # Registry value type
T = TypeVar("T")  # Generic / success type
R = TypeVar("R")  # Return / transformed type

Priority: TypeAlias = int  # Numeric boot-order priority for providers

__all__ = [
    "K",
    "Priority",
    "R",
    "T",
    "V",
]
