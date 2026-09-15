"""Shared pytest configuration for the generated public workspace."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any, TYPE_CHECKING

import pkgutil
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

_ROOT = Path(__file__).parent

# The generated workspace has only public package source directories. Add them
# explicitly so tests also work when the checkout is not installed editable.
for _src in sorted(_ROOT.glob("*/*/src")):
    _src_str = str(_src)
    if _src_str not in sys.path:
        sys.path.insert(0, _src_str)

import quadkit as _quadkit  # noqa: E402
import quadkit.contracts as _quadkit_contracts  # noqa: E402

for _namespace, _package in (
    ("quadkit", _quadkit),
    ("quadkit.contracts", _quadkit_contracts),
):
    if hasattr(_package, "__path__"):
        _package.__path__ = pkgutil.extend_path(list(_package.__path__), _namespace)

pytest_plugins = ["quadkit.testing.integration.fixtures", "pytest_asyncio"]


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio for anyio-based public tests."""
    return "asyncio"


@pytest.fixture
def setup_container_context() -> Generator[Any, None, None]:
    """Provide a container in the public context registry for a test."""
    from quadkit.di import Container
    from quadkit.primitives.context import create_default_context

    container = Container()
    context = create_default_context()
    token = context.set_dynamic("container", container)
    yield container
    context.reset_dynamic("container", token)


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> dict[str, object]:
    """Close asyncio's default executor after each public async test."""

    del config, item

    def _factory() -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        original_close = loop.close

        def _close() -> None:
            if not loop.is_closed() and not loop.is_running():
                try:
                    loop.run_until_complete(loop.shutdown_default_executor())
                except Exception:  # noqa: BLE001 - best-effort test cleanup
                    pass
            original_close()

        loop.close = _close  # type: ignore[method-assign]
        return loop

    return {"default": _factory}
