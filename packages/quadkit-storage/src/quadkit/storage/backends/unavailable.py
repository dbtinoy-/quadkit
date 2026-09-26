"""Stub generators for unavailable storage drivers."""

from __future__ import annotations

from typing import Any


def _make_unavailable_class(name: str, install_hint: str) -> type:
    """Create a stub class that raises an informative ImportError on use."""

    class _UnavailableDriver:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                f"{name} is not available.  Install the required package:\n"
                f"    {install_hint}"
            )

    _UnavailableDriver.__name__ = name
    _UnavailableDriver.__qualname__ = name
    return _UnavailableDriver
