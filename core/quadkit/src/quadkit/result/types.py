"""Result type — backward-compatible re-export.

Canonical location: quadkit.contracts.core.result
"""

from __future__ import annotations

from quadkit.contracts.core.result import Err as Err
from quadkit.contracts.core.result import Ok as Ok
from quadkit.contracts.core.result import Result as Result
from quadkit.contracts.core.result import UnwrapError as UnwrapError

__all__ = ["Err", "Ok", "Result"]
