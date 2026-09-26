"""Provider lifecycle — wires repositories and services into DI.

The provider is the bridge between the framework's DI container and
your application code.  ``register()`` binds services, ``boot()``
performs post-registration setup, ``shutdown()`` cleans up.

Simplest patterns for new users:
  - register() creates instances and binds them into the container
  - boot() runs after all providers are registered (for cross-cutting setup)
  - shutdown() cleans up resources (close connections, flush buffers)
"""

from __future__ import annotations

from taskapp.di.provider import TaskProvider

__all__ = ["TaskProvider"]
