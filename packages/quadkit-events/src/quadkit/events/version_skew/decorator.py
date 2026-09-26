"""@known_events decorator for declarative known-event-set registration."""

from __future__ import annotations

from collections.abc import Callable

from quadkit.events.version_skew.registry import KnownEventSetRegistry


def known_events(consumer_id: str) -> Callable[[type], type]:
    """Class decorator that registers a known event set.

    Reads ``KNOWN: list[EventTypeVersion]`` from the decorated class.

    Raises:
        TypeError: If the class does not define ``KNOWN``.
    """

    def decorator(cls: type) -> type:
        raw = getattr(cls, "KNOWN", None)
        if raw is None:
            raise TypeError(
                f"{cls.__name__} decorated with @known_events but "
                f"does not define a KNOWN class attribute",
            )
        registry = KnownEventSetRegistry(consumer_id=consumer_id)
        registry.register(list(raw))
        cls.__known_event_registry__ = registry  # type: ignore[attr-defined]
        return cls

    return decorator


__all__ = ["known_events"]
