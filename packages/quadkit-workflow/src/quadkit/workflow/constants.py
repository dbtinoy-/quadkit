"""Constants for the execution subsystem.

Defaults for bulk operation batching, pipeline timeouts, and graph engine.
"""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-workflow")
except ImportError:
    __version__ = "0.0.0"

DEFAULT_BULK_BATCH_SIZE: int = (
    100  # consumed by: BulkOperationConfig.batch_size (workflow provider default)
)
DEFAULT_BULK_CONCURRENCY: int = (
    10  # consumed by: BulkOperationConfig.max_concurrency (workflow provider default)
)
DEFAULT_BULK_TIMEOUT: float = 300.0  # seconds — consumed by: BulkOperationConfig.timeout (workflow provider default)
DEFAULT_PIPELINE_TIMEOUT: float = (
    60.0  # seconds — consumed by: BulkOperationConfig.pipeline_timeout
)

# Graph engine defaults (from the optional provider)
DEFAULT_GRAPH_MAX_ITERATIONS: int = 25
DEFAULT_GRAPH_NODE_TIMEOUT: float = 120.0
GRAPH_ENV_PREFIX: str = "QK_WORKFLOW__GRAPH__"

__all__ = [
    "DEFAULT_BULK_BATCH_SIZE",
    "DEFAULT_BULK_CONCURRENCY",
    "DEFAULT_BULK_TIMEOUT",
    "DEFAULT_GRAPH_MAX_ITERATIONS",
    "DEFAULT_GRAPH_NODE_TIMEOUT",
    "DEFAULT_PIPELINE_TIMEOUT",
    "GRAPH_ENV_PREFIX",
]
