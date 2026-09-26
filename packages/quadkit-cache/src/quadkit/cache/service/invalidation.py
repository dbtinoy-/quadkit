"""Tag-based and pattern invalidation mixin.

This module provides the :class:`InvalidationMixin` which adds tag-indexed bulk
invalidation to :class:`CacheService`.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, cast

from quadkit.logging import get_logger

logger = get_logger(__name__)

_BACKEND_ERRORS = (
    RuntimeError,
    OSError,
    ConnectionError,
    ValueError,
    AttributeError,
)


class InvalidationMixin:
    """Mixin providing tag-based cache invalidation for CacheService.

    Requires the host class to provide ``set``, ``delete_many``, and
    ``_tag_index``.
    """

    # Declared here so type checkers understand the required host attributes;
    # the actual values are set by CacheService.__init__.
    _tag_index: OrderedDict[str, set[str]]
    _max_tags: int

    async def set_with_tags(
        self,
        key: str,
        value: Any,
        tags: list[str],
        ttl: int | None = None,
        backend: str | None = None,
    ) -> bool:
        """Set a value in cache and associate it with one or more tags.

        Tags can later be used with :meth:`invalidate_by_tag` to bulk-invalidate
        all cache entries that share a tag (e.g. all entries for ``"user:123"``).

        Args:
            key: Cache key.
            value: Value to cache.
            tags: List of tag strings to associate with the key.
            ttl: Time-to-live in seconds.
            backend: Named backend (uses default if ``None``).

        Returns:
            ``True`` if the value was stored successfully, ``False`` otherwise.
        """
        success = await self.set(key, value, ttl=ttl, backend=backend)  # type: ignore[attr-defined]
        if success:
            for tag in tags:
                if tag not in self._tag_index:
                    if len(self._tag_index) >= self._max_tags:
                        self._tag_index.popitem(last=False)  # evict oldest
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)
                self._tag_index.move_to_end(tag)  # mark as recently used
        return cast("bool", success)

    async def invalidate_by_tag(
        self,
        tag: str,
        backend: str | None = None,
    ) -> int:
        """Delete all cache keys associated with *tag*.

        Keys are tracked in an in-memory index populated by :meth:`set_with_tags`.
        The tag index entry is cleared after invalidation.

        Args:
            tag: The tag whose associated keys should be deleted.
            backend: Named backend (uses default if ``None``).

        Returns:
            The number of keys deleted.
        """
        keys = list(self._tag_index.pop(tag, set()))
        if not keys:
            return 0
        try:
            await self.delete_many(keys, backend=backend)  # type: ignore[attr-defined]
        except _BACKEND_ERRORS as e:
            logger.warning("invalidate_by_tag failed for tag '%s': %s", tag, e)
            return 0
        return len(keys)
