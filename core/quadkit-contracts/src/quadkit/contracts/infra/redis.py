"""Redis client surface driven directly by Quadkit.

Most Quadkit packages talk to Redis through
:class:`~quadkit.contracts.infra.cache.CacheBackendProtocol`; a few need the
raw client because the command has to be atomic or is not a key/value read —
the Lua token bucket in ``quadkit-web``, the released-by-script locks in
``quadkit-cache`` and the sorted-set windows in ``the optional provider``.

:class:`RedisClientProtocol` names the commands those call sites issue, so a
client can be injected, registered and resolved as a typed dependency instead
of ``Any``. It mirrors the ``redis.asyncio`` client of redis-py, which is the
implementation the framework ships against.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

__all__ = ["RedisClientProtocol"]


class RedisClientProtocol(Protocol):
    """The commands Quadkit issues against a raw Redis client.

    Structural by design: ``redis.asyncio.Redis``, ``fakeredis`` and purpose
    built doubles satisfy it without inheriting from it. Both the synchronous
    command methods below and the connection lifecycle stay the client's own;
    only what the framework calls is named here.

    The return values stay ``Any`` because every Redis command answers with the
    decoded payload of its own shape — callers narrow what they read.
    """

    async def eval(
        self,
        script: str,
        numkeys: int,
        *keys_and_args: Any,
    ) -> Any:
        """Run ``script`` server-side.

        Args:
            script: Lua source for the command.
            numkeys: How many of the following arguments are key names.
            *keys_and_args: Key names followed by the script arguments.

        Returns:
            Whatever the script returns.
        """
        ...

    async def get(self, name: str) -> Any:
        """Return the value stored at ``name``.

        Args:
            name: Key to read.

        Returns:
            The stored value, or ``None`` when the key is absent.
        """
        ...

    async def set(
        self,
        name: str,
        value: Any,
        *,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> Any:
        """Store ``value`` at ``name``.

        Args:
            name: Key to write.
            value: Payload to store.
            ex: Expiry in seconds.
            nx: Only write when the key does not exist.
            xx: Only write when the key already exists.

        Returns:
            The command result (``None``, or a truthy value under ``nx``/``xx``).
        """
        ...

    async def setex(self, name: str, time: int, value: Any) -> Any:
        """Store ``value`` at ``name`` with a lifetime.

        Args:
            name: Key to write.
            time: Lifetime in seconds.
            value: Payload to store.

        Returns:
            The command result.
        """
        ...

    async def expire(self, name: str, time: int) -> Any:
        """Set the lifetime of an existing key.

        Args:
            name: Key to expire.
            time: Lifetime in seconds.

        Returns:
            ``True`` when the timeout was applied.
        """
        ...

    async def zadd(self, name: str, mapping: Mapping[str, float]) -> Any:
        """Add members to the sorted set at ``name``.

        Args:
            name: Sorted-set key.
            mapping: Member name to score.

        Returns:
            How many members were newly added.
        """
        ...

    async def zcard(self, name: str) -> Any:
        """Count the members of the sorted set at ``name``.

        Args:
            name: Sorted-set key.

        Returns:
            The cardinality of the set.
        """
        ...

    async def zremrangebyscore(
        self,
        name: str,
        min: float | str,
        max: float | str,
    ) -> Any:
        """Drop sorted-set members whose score falls inside a range.

        Args:
            name: Sorted-set key.
            min: Inclusive lower score bound, or ``"-inf"``.
            max: Inclusive upper score bound, or ``"+inf"``.

        Returns:
            How many members were removed.
        """
        ...
