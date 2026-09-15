"""Reactive stream operators."""

# Operators deliberately re-export builtin-named functions (RxPY convention).
# ruff: noqa: A004

from __future__ import annotations

from quadkit.reactive.operators.control import catch, merge, on_end, skip, take
from quadkit.reactive.operators.time_ops import buffer, debounce, throttle, window
from quadkit.reactive.operators.transform import (
    distinct,
    filter,
    map,
    scan,
)

__all__ = [
    "buffer",
    "catch",
    "debounce",
    "distinct",
    "filter",
    "map",
    "merge",
    "on_end",
    "scan",
    "skip",
    "take",
    "throttle",
    "window",
]
