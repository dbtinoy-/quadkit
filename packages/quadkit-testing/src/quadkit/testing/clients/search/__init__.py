"""
Search testing infrastructure.

Provides modular testing components for search functionality,
following the established pattern across Quadkit Framework packages.
"""

from __future__ import annotations

# Core testing classes and data
from quadkit.testing.clients.search.client import (
    MockSearchBackend,
    SearchTestBed,
    SearchTestClient,
    SearchTestData,
)

# Pytest fixtures
from quadkit.testing.clients.search.fixtures import (
    mock_search_engine,
    search_backend,
    search_test_bed,
    search_test_client,
)

# Legacy compatibility - direct exports for backward compatibility
__all__ = [
    # Mock components
    "MockSearchBackend",
    # Test infrastructure
    "SearchTestBed",
    "SearchTestClient",
    # Test data
    "SearchTestData",
    "mock_search_engine",
    "search_backend",
    # Fixtures
    "search_test_bed",
    "search_test_client",
]
