"""Reactive layer exceptions."""

from __future__ import annotations

from quadkit.contracts.exceptions.base import QuadkitError


class ReactiveError(QuadkitError):
    """Base exception for the reactive stream layer."""

    _code = "QK_ERR_CORE_006"


class BackpressureError(ReactiveError):
    """Raised when a subscriber channel overflows under a non-blocking policy."""

    _code = "QK_ERR_CORE_007"
