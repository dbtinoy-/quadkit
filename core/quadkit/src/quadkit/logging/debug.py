"""Debug mode utilities for Quadkit Framework lifecycle logging.

The ``QK_DEBUG`` environment variable corresponds to the ``debug``
field in :class:`~quadkit.config.main.QuadkitConfig`. This module reads
it directly for early-boot usage before the config system has been
initialized. At runtime, ``QuadkitConfig.debug`` is the canonical source.
"""

from __future__ import annotations

import os
from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)


def is_debug_mode() -> bool:
    """Check if Quadkit debug mode is enabled.

    Reads the ``QK_DEBUG`` env var directly so this function works
    at early-boot time before config is loaded. The env var corresponds to
    ``QuadkitConfig.debug`` and is set consistently by the config system.
    """
    return os.environ.get("QK_DEBUG", "").strip() in ("1", "true", "yes")


def log_lifecycle(event: str, **context: Any) -> None:
    """Emit a structured lifecycle debug log."""
    if not is_debug_mode():
        return

    logger.debug(event, **context)


__all__ = ["is_debug_mode", "log_lifecycle"]
