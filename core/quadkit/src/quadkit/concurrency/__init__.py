"""Quadkit Concurrency — async task management and synchronization primitives.

Provides task management, parallel execution, dispatchers, bounded
channels, and synchronization primitives built on asyncio.  All
components are registered through the DI container via
:class:`ConcurrencyModule`.

The dispatcher runs CPU-bound and I/O-bound work in dedicated thread
pools; ``BoundedChannel`` brings Go-style backpressure to async
producer-consumer pipelines; ``AsyncRWLock`` provides fair read-write
locking without starvation.

Basic Usage::

    from quadkit.concurrency import ConcurrencyModule, ConcurrencyConfig

    @module(imports=[ConcurrencyModule.configure(ConcurrencyConfig())])
    class AppModule(Module):
        pass

Module Structure:
    - bridges: Sync/async bridge utilities (``SyncBridge``)
    - channels: Bounded async channels (``BoundedChannel``)
    - config: Configuration models (``ConcurrencyConfig``, ``DispatcherConfig``)
    - di: Dependency injection provider (``ConcurrencyProvider``)
    - exceptions: Concurrency exception hierarchy (``ConcurrencyError``, …)
    - executors: Task dispatcher, parallel executor, task manager
    - locks: Async read-write locks (``AsyncRWLock``)
    - module: ``ConcurrencyModule`` IoC registration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.concurrency.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.concurrency.bridges.sync_bridge import SyncBridge
    from quadkit.concurrency.channels.channel import BoundedChannel
    from quadkit.concurrency.config import (
        ConcurrencyConfig,
        DispatcherConfig,
        PoolConfig,
        ThreadPoolConfig,
    )
    from quadkit.concurrency.di.provider import ConcurrencyProvider
    from quadkit.concurrency.exceptions import (
        AsyncError,
        CancellationScopeError,
        ChannelClosedError,
        ChannelFullError,
        ConcurrencyError,
        DispatcherError,
        StructuredParallelismError,
        TaskGroupError,
    )
    from quadkit.concurrency.executors.dispatcher import (
        DispatcherImpl,
        dispatch,
        run_sync,
        shutdown_dispatcher,
    )
    from quadkit.concurrency.executors.parallel import Parallel
    from quadkit.concurrency.executors.task_manager import TaskManager
    from quadkit.concurrency.locks.rwlock import AsyncRWLock
    from quadkit.concurrency.module import ConcurrencyModule
    from quadkit.concurrency.task_utils import create_tracked_task
    from quadkit.contracts.core import (
        ExecutionStrategy,
        ParallelProtocol,
        TaskManagerProtocol,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # --- Task Utilities ---
    "create_tracked_task": (
        "quadkit.concurrency.task_utils",
        "create_tracked_task",
    ),
    # --- Module ---
    "ConcurrencyModule": ("quadkit.concurrency.module", "ConcurrencyModule"),
    # --- Config ---
    "ConcurrencyConfig": ("quadkit.concurrency.config", "ConcurrencyConfig"),
    "DispatcherConfig": ("quadkit.concurrency.config", "DispatcherConfig"),
    "PoolConfig": ("quadkit.concurrency.config", "PoolConfig"),
    "ThreadPoolConfig": ("quadkit.concurrency.config", "ThreadPoolConfig"),
    # --- Channels ---
    "BoundedChannel": ("quadkit.concurrency.channels.channel", "BoundedChannel"),
    # --- Locks ---
    "AsyncRWLock": ("quadkit.concurrency.locks.rwlock", "AsyncRWLock"),
    # --- Executors ---
    "DispatcherImpl": ("quadkit.concurrency.executors.dispatcher", "DispatcherImpl"),
    "dispatch": ("quadkit.concurrency.executors.dispatcher", "dispatch"),
    "run_sync": ("quadkit.concurrency.executors.dispatcher", "run_sync"),
    "shutdown_dispatcher": (
        "quadkit.concurrency.executors.dispatcher",
        "shutdown_dispatcher",
    ),
    "Parallel": ("quadkit.concurrency.executors.parallel", "Parallel"),
    "TaskManager": ("quadkit.concurrency.executors.task_manager", "TaskManager"),
    # --- Bridges ---
    "SyncBridge": ("quadkit.concurrency.bridges.sync_bridge", "SyncBridge"),
    # --- Exceptions ---
    "AsyncError": ("quadkit.concurrency.exceptions", "AsyncError"),
    "CancellationScopeError": (
        "quadkit.concurrency.exceptions",
        "CancellationScopeError",
    ),
    "ChannelClosedError": ("quadkit.concurrency.exceptions", "ChannelClosedError"),
    "ChannelFullError": ("quadkit.concurrency.exceptions", "ChannelFullError"),
    "ConcurrencyError": ("quadkit.concurrency.exceptions", "ConcurrencyError"),
    "DispatcherError": ("quadkit.concurrency.exceptions", "DispatcherError"),
    "StructuredParallelismError": (
        "quadkit.concurrency.exceptions",
        "StructuredParallelismError",
    ),
    "TaskGroupError": ("quadkit.concurrency.exceptions", "TaskGroupError"),
    # --- Contracts (re-exported for convenience) ---
    "ExecutionStrategy": ("quadkit.contracts.core", "ExecutionStrategy"),
    "ParallelProtocol": ("quadkit.contracts.core", "ParallelProtocol"),
    "TaskManagerProtocol": ("quadkit.contracts.core", "TaskManagerProtocol"),
    # --- Provider ---
    "ConcurrencyProvider": ("quadkit.concurrency.di.provider", "ConcurrencyProvider"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "AsyncError",
    "AsyncRWLock",
    "BoundedChannel",
    "CancellationScopeError",
    "ChannelClosedError",
    "ChannelFullError",
    "ConcurrencyConfig",
    "ConcurrencyError",
    "ConcurrencyModule",
    "ConcurrencyProvider",
    "DispatcherConfig",
    "DispatcherError",
    "DispatcherImpl",
    "ExecutionStrategy",
    "Parallel",
    "ParallelProtocol",
    "PoolConfig",
    "StructuredParallelismError",
    "SyncBridge",
    "TaskGroupError",
    "TaskManager",
    "TaskManagerProtocol",
    "ThreadPoolConfig",
    "create_tracked_task",
    "dispatch",
    "run_sync",
    "shutdown_dispatcher",
]
