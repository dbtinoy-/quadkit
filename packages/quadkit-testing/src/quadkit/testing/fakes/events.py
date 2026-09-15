"""Fake event bus for recording and asserting on published domain events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.contracts.domain.events import DomainEvent

__all__ = ["FakeEventBus"]

T = TypeVar("T")

_SENTINEL = object()


class FakeEventBus:
    """Records all published events for test assertions.

    Satisfies the ``EventBusProtocol`` protocol from ``quadkit.contracts.events``.

    Example::

        bus = FakeEventBus()
        await bus.publish(UserCreated(user_id="abc"))
        bus.assert_published(UserCreated, count=1, user_id="abc")
    """

    def __init__(self) -> None:
        self._published: list[DomainEvent] = []
        self._handlers: dict[type, list[tuple[int, Any]]] = {}

    # -- EventBusProtocol protocol -------------------------------------------------

    def subscribe(
        self,
        event_type: type,
        handler: Any,
        priority: int = 0,
    ) -> None:
        """Register *handler* for *event_type*."""
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append((priority, handler))
        handlers.sort(key=lambda h: h[0])

    def unsubscribe(self, event_type: type, handler: Any) -> None:
        """Remove *handler* for *event_type*."""
        handlers = self._handlers.get(event_type, [])
        self._handlers[event_type] = [(p, h) for p, h in handlers if h is not handler]

    async def publish(self, event: Any) -> None:
        """Record *event* and dispatch to any registered handlers."""
        self._published.append(event)
        handlers = self._handlers.get(type(event), [])
        for _, handler in handlers:
            if hasattr(handler, "handle"):
                await handler.handle(event)
            else:
                await handler(event)

    # -- Query helpers -----------------------------------------------------

    @property
    def published(self) -> list[DomainEvent]:
        """All published events."""
        return list(self._published)

    def published_of_type(self, event_type: type[T]) -> list[T]:
        """Return published events matching *event_type*."""
        return [e for e in self._published if isinstance(e, event_type)]

    # -- Assertion helpers -------------------------------------------------

    def assert_published(
        self,
        event_type: type[T],
        count: int | None = None,
        **attrs: Any,
    ) -> None:
        """Assert that *event_type* was published.

        Optionally verify *count* and attribute values.
        """
        matches: list[T] = self.published_of_type(event_type)
        if not matches:
            published_types = [type(e).__name__ for e in self._published]
            msg = (
                f"Expected {event_type.__name__} to be published but "
                f"found: {published_types}"
            )
            raise AssertionError(msg)

        if count is not None and len(matches) != count:
            msg = (
                f"Expected {count} {event_type.__name__} event(s) but "
                f"found {len(matches)}"
            )
            raise AssertionError(msg)

        if attrs:
            for event in matches:
                if all(getattr(event, k, _SENTINEL) == v for k, v in attrs.items()):
                    return
            msg = f"No {event_type.__name__} event matched attributes {attrs}"
            raise AssertionError(msg)

    def assert_not_published(self, event_type: type[T]) -> None:
        """Assert that *event_type* was NOT published."""
        matches: list[T] = self.published_of_type(event_type)
        if matches:
            msg = (
                f"Expected {event_type.__name__} to NOT be published "
                f"but found {len(matches)} instance(s)"
            )
            raise AssertionError(msg)

    def assert_published_once(self, event_type: type, **attrs: Any) -> None:
        """Assert exactly one *event_type* was published."""
        self.assert_published(event_type, count=1, **attrs)

    def assert_events_in_order(self, *event_types: type) -> None:
        """Assert that events were published in the given positional order.

        Checks that position ``i`` in the published event stream matches
        ``event_types[i]``.  Use :meth:`assert_published` to verify events
        that may appear anywhere in the stream.

        Args:
            *event_types: Sequence of event types in the expected order.

        Raises:
            AssertionError: If any position does not match or the stream is
                shorter than the expected sequence.

        Example::

            await bus.publish(UserRegistered(user_id="1"))
            await bus.publish(EmailSent(user_id="1"))
            bus.assert_events_in_order(UserRegistered, EmailSent)
        """
        published_types = [type(e) for e in self._published]
        for i, expected in enumerate(event_types):
            if i >= len(published_types):
                raise AssertionError(
                    f"Expected event at position {i}: {expected.__name__}, "
                    f"but only {len(published_types)} event(s) were published."
                )
            actual = published_types[i]
            if actual is not expected:
                raise AssertionError(
                    f"Event order mismatch at position {i}: "
                    f"expected {expected.__name__}, got {actual.__name__}."
                )

    def clear(self) -> None:
        """Reset the recorded events list."""
        self._published.clear()
