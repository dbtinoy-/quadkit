"""Cron expression parsing utilities.

This module provides utilities for parsing and working with cron expressions.

Optional dependency
-------------------
:class:`CronExpression` requires the ``croniter`` package, which is an
**optional** dependency of ``quadkit-tasks``.  Install it with::

    pip install croniter

or::

    pip install "quadkit-tasks[cron]"

When ``croniter`` is not installed the module itself can be imported without
error; only *instantiating* :class:`CronExpression` raises ``ImportError``
with a helpful message.
"""

from __future__ import annotations

import time
from typing import Any

# Optional croniter dependency
croniter: Any | None = None
HAS_CRONITER = False
try:
    import croniter as _croniter
except ImportError:
    croniter = None
else:
    croniter = _croniter
    HAS_CRONITER = True


class CronExpression:
    """Wrapper for cron expression parsing.

    Provides a unified interface for cron expression handling
    with optional croniter dependency.

    .. note::
        This class requires the ``croniter`` optional dependency.
        See :mod:`quadkit.tasks.scheduling.cron` for installation instructions.
        Instantiation raises :exc:`ImportError` when ``croniter`` is absent.

    Example:
        ```python
        cron = CronExpression("0 9 * * 1-5")  # Weekdays at 9am
        next_run = cron.get_next()
        ```
    """

    def __init__(self, expression: str):
        """Initialize cron expression

        Args:
            expression: Cron expression string

        Raises:
            ImportError: If croniter is not installed
            ValueError: If expression is invalid
        """
        if not HAS_CRONITER:
            raise ImportError(
                "croniter is required for cron scheduling. "
                "Install with: pip install croniter",
            )

        self.expression = expression
        self._validate()

    def _validate(self) -> None:
        """Validate cron expression

        Raises:
            ValueError: If expression is invalid
        """
        try:
            # Ensure mypy knows croniter is available (guarded by HAS_CRONITER in __init__)
            assert croniter is not None  # noqa: S101  # guarded by HAS_CRONITER import gate
            croniter.croniter(self.expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{self.expression}': {e}") from e

    def get_next(self, base_time: float | None = None) -> float:
        """Get next execution time

        Args:
            base_time: Base time (defaults to current time)

        Returns:
            Unix timestamp of next execution
        """
        if base_time is None:
            base_time = time.time()

        # Assert to help the type checker that croniter is not None
        assert croniter is not None  # noqa: S101  # guarded by HAS_CRONITER import gate
        cron = croniter.croniter(self.expression, base_time)
        return float(cron.get_next())

    def get_prev(self, base_time: float | None = None) -> float:
        """Get previous execution time

        Args:
            base_time: Base time (defaults to current time)

        Returns:
            Unix timestamp of previous execution
        """
        if base_time is None:
            base_time = time.time()

        # Assert to help the type checker that croniter is not None
        assert croniter is not None  # noqa: S101  # guarded by HAS_CRONITER import gate
        cron = croniter.croniter(self.expression, base_time)
        return float(cron.get_prev())

    def __str__(self) -> str:
        """String representation"""
        return self.expression

    def __repr__(self) -> str:
        """Developer representation"""
        return f"CronExpression('{self.expression}')"
