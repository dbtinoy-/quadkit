"""Header helper utilities.

Pure functions for normalising and merging HTTP headers — no framework
dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


def parse_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    """Normalise HTTP headers: lowercase keys, strip whitespace from values.

    Args:
        headers: Any mapping of header values.

    Returns:
        Normalised ``dict[str, str]``.

    Example:
        >>> parse_headers({"Content-Type": " application/json "})
        {'content-type': 'application/json'}
    """
    return {k.lower(): str(v).strip() for k, v in headers.items()}


def merge_headers(
    *header_dicts: Mapping[str, Any],
    normalize: bool = True,
) -> dict[str, str]:
    """Merge multiple header mappings; later entries win on duplicate keys.

    Args:
        *header_dicts: One or more header mappings to merge.
        normalize: When ``True``, lowercase keys and strip values (default).

    Returns:
        Merged ``dict[str, str]``.
    """
    merged: dict[str, str] = {}
    for headers in header_dicts:
        if headers:
            for k, v in headers.items():
                merged[k] = str(v)
    if normalize:
        merged = parse_headers(merged)
    return merged


__all__ = ["merge_headers", "parse_headers"]
