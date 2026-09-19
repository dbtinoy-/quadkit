"""Decorators for security enforcement — input sanitization."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.security.sanitization import InputSanitizer

F = TypeVar("F", bound=Callable[..., Any])

__all__ = [
    "sanitize_input",
]


def sanitize_input(
    *fields: str,
    sanitizer: InputSanitizer | None = None,
) -> Callable[[F], F]:
    """Sanitize the specified string keyword arguments before the handler executes.

    Uses :class:`~quadkit.security.sanitization.InputSanitizer` to strip
    dangerous HTML/script content from the named kwargs. Non-string values and
    absent fields are passed through unchanged. An ``InputSanitizer`` is
    instantiated with default config when *sanitizer* is not provided.

    Args:
        *fields: Names of keyword arguments to sanitize. Each named field whose
            value is a ``str`` will be run through ``InputSanitizer.sanitize``.
        sanitizer: Optional pre-configured :class:`InputSanitizer` instance.
            When ``None``, a default instance is created once at decoration time.

    Returns:
        Decorator that wraps async and sync handlers with input sanitization.

    Example::

        @sanitize_input("comment", "bio")
        async def update_profile(
            self, user_id: str, comment: str, bio: str
        ) -> Profile:
            return await self.repo.update(user_id, comment=comment, bio=bio)
    """

    def decorator(fn: F) -> F:
        from quadkit.security.sanitization import (
            InputSanitizer as _InputSanitizer,  # noqa: PLC0415
        )

        _sanitizer = sanitizer or _InputSanitizer()

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                for field in fields:
                    if field in kwargs and isinstance(kwargs[field], str):
                        kwargs[field] = _sanitizer.sanitize(kwargs[field])
                return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            for field in fields:
                if field in kwargs and isinstance(kwargs[field], str):
                    kwargs[field] = _sanitizer.sanitize(kwargs[field])
            return fn(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator
