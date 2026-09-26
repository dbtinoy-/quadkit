"""
Runtime validation utilities for protocols and type safety.

This package provides utilities to validate protocol implementations
at runtime, preventing AttributeError from incomplete implementations.
"""

from __future__ import annotations

from quadkit.sql.validation.protocols import (
    ProtocolValidationError,
    ensure_protocol,
    validate_protocol,
)

__all__ = [
    "ProtocolValidationError",
    "ensure_protocol",
    "validate_protocol",
]
