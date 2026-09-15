"""Search type aliases.

Type aliases for search operations.
"""

from __future__ import annotations

from typing import Any

# Type aliases
DocumentData = dict[str, Any]
IndexSettings = dict[str, Any]
SearchFilters = dict[str, Any]


__all__ = ["DocumentData", "IndexSettings", "SearchFilters"]
