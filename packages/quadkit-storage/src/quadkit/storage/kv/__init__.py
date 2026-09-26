"""Quadkit Storage KV backends.

This package provides :class:`~quadkit.contracts.StorageBackend`
implementations for simple key-value storage needs.

Backends
--------
.. list-table::
   :header-rows: 1

   * - Class
     - Type
     - Notes
   * - :class:`InMemoryKVStorage`
     - ``memory``
     - In-process dict; ephemeral; no external deps.  TTL is lazy.
   * - :class:`LocalStorage`
     - ``file``
     - File-backed JSON store; atomic writes; TTL is lazy.
"""

from __future__ import annotations

from quadkit.storage.kv.local import LocalStorage
from quadkit.storage.kv.memory import InMemoryKVStorage

__all__ = [
    "InMemoryKVStorage",
    "LocalStorage",
]
