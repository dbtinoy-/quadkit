"""Package-level constants for the quadkit framework.

Single source of truth for version metadata and the minimum Python version.
"""

from __future__ import annotations

import importlib.metadata
import sys

try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Python version guard
# ---------------------------------------------------------------------------

MIN_PYTHON_VERSION: tuple[int, int] = (3, 11)

if sys.version_info < MIN_PYTHON_VERSION:
    _major, _minor = MIN_PYTHON_VERSION
    raise RuntimeError(
        f"quadkit requires Python {_major}.{_minor}+, "
        f"but running Python {sys.version_info.major}.{sys.version_info.minor}"
    )

__all__ = ["MIN_PYTHON_VERSION", "__version__"]
