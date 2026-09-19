"""Quadkit Reactive — native stream composition for async apps.

Example:
    ```python
    from quadkit.reactive import Stream, ops

    async def gen():
        yield 1
        yield 2

    async def main():
        stream = Stream(gen())
        async for item in stream.pipe(ops.map(lambda x: x * 2)):
            print(item)
    ```
"""

from __future__ import annotations

from quadkit.reactive import operators as ops
from quadkit.reactive.core import EventStream, Op, Stream
from quadkit.reactive.exceptions import BackpressureError, ReactiveError
from quadkit.reactive.subjects import Subject, Subscription, share

__all__ = [
    "BackpressureError",
    "EventStream",
    "Op",
    "ReactiveError",
    "Stream",
    "Subject",
    "Subscription",
    "ops",
    "share",
]
