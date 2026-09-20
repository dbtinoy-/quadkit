"""Pytest plugin package for Quadkit testing.

The plugin itself lives in :mod:`quadkit.testing.plugins.pytest.plugin`, which
the `pytest11` entry point loads. Importing it from here keeps
`from quadkit.testing.plugins.pytest import pytest_collection_modifyitems`
working for tests and tooling that address the package.
"""

from __future__ import annotations

from quadkit.testing.plugins.pytest.plugin import (
    _CHECK_TIMEOUT,
    _MARKERS,
    _SERVICE_ENDPOINTS,
    _available_fixture_plugins,
    _check_service,
    pytest_collection_modifyitems,
    pytest_configure,
    pytest_plugins,
)

__all__ = [
    "_CHECK_TIMEOUT",
    "_MARKERS",
    "_SERVICE_ENDPOINTS",
    "_available_fixture_plugins",
    "_check_service",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_plugins",
]
