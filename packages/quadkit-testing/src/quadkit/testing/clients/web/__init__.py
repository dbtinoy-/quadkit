"""Test client for Quadkit Web applications."""

from __future__ import annotations

try:
    from quadkit.testing.clients.web.bed import WebTestBed, with_web
    from quadkit.testing.clients.web.client import TestResponse, WebTestClient
except ImportError:
    WebTestBed = None  # type: ignore[assignment,misc]
    WebTestClient = None  # type: ignore[assignment,misc]
    TestResponse = None  # type: ignore[assignment,misc]
    with_web = None  # type: ignore[assignment]

__all__ = ["TestResponse", "WebTestBed", "WebTestClient", "with_web"]
