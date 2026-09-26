"""Projections module for read models.

This module provides:
- ProjectionProtocol: Base class for read model projections
- ProjectionManager: Manage projection updates and rebuilds
"""

from __future__ import annotations

from quadkit.events.projections.base import ProjectionProtocol, ProjectionStatus
from quadkit.events.projections.manager import ProjectionManager

__all__ = [
    "ProjectionManager",
    "ProjectionProtocol",
    "ProjectionStatus",
]
