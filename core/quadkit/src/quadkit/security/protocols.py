"""Re-exports for the security subsystem.

Re-exports ``GuardError`` from contracts.  The ``GuardProtocol``
is imported from ``quadkit.contracts.web.guard``.
"""

from __future__ import annotations

from quadkit.contracts.ai.exceptions import (
    GuardError as GuardError,  # re-export
)

__all__ = [
    "GuardError",
]
