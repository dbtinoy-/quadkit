"""Result pattern — concrete Ok/Err implementation and utility functions.

Canonical import path for all callers::

    from quadkit.result import Result, Ok, Err
    from quadkit.result import as_result, as_result_sync, collect, partition
    from quadkit.result import ResultPipeline, pipeline
    from quadkit.result import try_catch, try_catch_sync
"""

from __future__ import annotations

from quadkit.result._pipeline import ResultPipeline, pipeline
from quadkit.result.errors import ResultError, UnwrapError
from quadkit.result.types import Err, Ok, Result
from quadkit.result.utils import (
    as_result,
    as_result_sync,
    collect,
    partition,
    try_catch,
    try_catch_sync,
)

__all__ = [
    "Err",
    "Ok",
    "Result",
    "ResultError",
    "ResultPipeline",
    "UnwrapError",
    "as_result",
    "as_result_sync",
    "collect",
    "partition",
    "pipeline",
    "try_catch",
    "try_catch_sync",
]
