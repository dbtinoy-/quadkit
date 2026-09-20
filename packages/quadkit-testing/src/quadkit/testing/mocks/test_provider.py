"""Lifecycle-tracking test provider for verifying container boot sequences.

Unlike :class:`~quadkit.testing.mocks.base.MockProvider` (which provides a
mock base for real providers), ``TestProvider`` is a pure no-op provider
whose sole purpose is to record which lifecycle methods were invoked.

Example::

    provider = TestProvider(name="my_svc")
    await container.register(provider)
    assert provider.register_called
    assert not provider.boot_called
"""

from __future__ import annotations

from typing import Any

from quadkit.di.provider import Provider


class LifecycleTracker(Provider):
    """No-op provider that records lifecycle calls for assertions.

    .. note:: This class was renamed from ``TestProvider`` to avoid pytest
        collecting it as a test class.
    """

    __test__ = False  # Mark as non-test class to avoid pytest collection

    def __init__(self, name: str = "test", **kwargs: Any) -> None:
        super().__init__(name=name, **kwargs)
        self.register_called: bool = False
        self.boot_called: bool = False
        self.shutdown_called: bool = False

    async def register(self, container: Any) -> None:
        """Record that ``register`` was invoked."""
        self.register_called = True

    async def boot(self, container: Any) -> None:
        """Record that ``boot`` was invoked."""
        self.boot_called = True

    async def shutdown(self) -> None:
        """Record that ``shutdown`` was invoked."""
        self.shutdown_called = True

    def reset(self) -> None:
        """Clear all lifecycle flags."""
        self.register_called = False
        self.boot_called = False
        self.shutdown_called = False
