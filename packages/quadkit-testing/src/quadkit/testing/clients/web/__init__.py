"""Test client for Quadkit Web applications."""

from __future__ import annotations

from typing import Any, Final

from quadkit.testing._lazy_exports import resolve_export

_LAZY_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "TestResponse": ("quadkit.testing.clients.web.client", "TestResponse"),
    "WebTestBed": ("quadkit.testing.clients.web.bed", "WebTestBed"),
    "WebTestClient": ("quadkit.testing.clients.web.client", "WebTestClient"),
    "with_web": ("quadkit.testing.clients.web.bed", "with_web"),
}

# The beds need the test client stack, which ships with the web extra only.
_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset(
    {
        "quadkit.testing.clients.web.bed",
        "quadkit.testing.clients.web.client",
    }
)


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    return resolve_export(
        name,
        _LAZY_IMPORTS,
        package=__name__,
        optional=_OPTIONAL_MODULES,
    )


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


__all__ = [
    "TestResponse",
    "WebTestBed",
    "WebTestClient",
    "with_web",
]
