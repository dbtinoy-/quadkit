"""Background tasks for fire-and-forget operations."""

from __future__ import annotations

from quadkit.web.background.decorator import background
from quadkit.web.background.tasks import (
    BackgroundTasks,
    BackgroundTaskScope,
    StarletteBackgroundTaskRunner,
)

__all__ = [
    "BackgroundTaskScope",
    "BackgroundTasks",
    "StarletteBackgroundTaskRunner",
    "background",
]
