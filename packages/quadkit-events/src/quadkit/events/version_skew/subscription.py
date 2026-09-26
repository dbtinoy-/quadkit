"""Version-aware subscription wrapper with skew alerting.

Composes with SchemaEvolution: if evolution can migrate an unknown version
to a known one, it does (no alert). Truly-unknown types/versions trigger
alerts via AlertDispatcherProtocol.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.events.version_skew import (
    EventSchemaVersionSkew,
    UnknownEventTypeReceived,
)
from quadkit.events.version_skew.registry import KnownEventSetRegistry

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from quadkit.contracts.events import EventBusProtocol
    from quadkit.contracts.observability.metrics import AlertDispatcherProtocol
    from quadkit.events.schema.evolution import SchemaEvolution


class VersionAwareSubscription:
    """Wraps an EventBus subscription with type+version verification.

    Decision tree on incoming event:
    1. Is ``(event_type, version)`` in ``known_set``? -> invoke handler.
    2. Is the type known but version unknown?
       -> try ``evolution.get_migration_path()``. If path exists,
         migrate the data and invoke handler. If no path, emit
         ``EventSchemaVersionSkew`` alert.
    3. Is the type completely unknown?
       -> emit ``UnknownEventTypeReceived`` alert.
    """

    def __init__(
        self,
        consumer_id: str,
        bus: EventBusProtocol,
        known_set: KnownEventSetRegistry,
        evolution: SchemaEvolution | None,
        alert_dispatcher: AlertDispatcherProtocol,
    ) -> None:
        self._consumer_id = consumer_id
        self._bus = bus
        self._known_set = known_set
        self._evolution = evolution
        self._alert_dispatcher = alert_dispatcher

    async def subscribe(
        self,
        event_type_pattern: str,
        handler: Callable[[Any], Awaitable[None]],
    ) -> None:
        wrapped = self._wrap_handler(handler)
        self._bus.subscribe(event_type_pattern, wrapped)  # type: ignore[arg-type]

    def _wrap_handler(
        self, handler: Callable[[Any], Awaitable[None]]
    ) -> Callable[[Any], Coroutine[None, None, None]]:
        async def wrapped(envelope: Any) -> None:
            await self._handle(envelope, handler)

        return wrapped

    async def _handle(
        self, envelope: Any, handler: Callable[[Any], Awaitable[None]]
    ) -> None:
        event_type: str = cast("str", getattr(envelope, "event_type", None))
        version = getattr(envelope, "version", 1)
        event_id = str(getattr(envelope, "event_id", ""))
        timestamp = getattr(envelope, "timestamp", datetime.now(UTC))
        metadata = getattr(envelope, "metadata", {}) or {}
        tenant_id = metadata.get("tenant_id") if isinstance(metadata, dict) else None

        if self._known_set.is_known(event_type, version):
            await handler(envelope)
            return

        if self._known_set.has_type(event_type):
            if self._evolution is not None:
                known_versions = [
                    t.schema_version
                    for t in self._known_set.all_known
                    if t.event_type == event_type
                ]
                target_version = max(known_versions) if known_versions else version

                if target_version != version:
                    path = await self._evolution.get_migration_path(
                        event_type, version, target_version
                    )
                    if path is not None and path.steps:
                        data = getattr(envelope, "event_data", None)
                        if data is not None:
                            migrated = await self._evolution.migrate_data(
                                event_type, dict(data), version, target_version
                            )
                            envelope.event_data = migrated
                        envelope.version = target_version
                        await handler(envelope)
                        return

            known_versions_set: frozenset[int] = frozenset(
                t.schema_version
                for t in self._known_set.all_known
                if t.event_type == event_type
            )
            alert = EventSchemaVersionSkew(
                consumer_id=self._consumer_id,
                event_type=event_type,
                received_version=version,
                known_versions=known_versions_set,
                upcast_attempted=self._evolution is not None,
                event_id=event_id,
                tenant_id=tenant_id,
                received_at=timestamp,
            )
            await self._alert_dispatcher.send_alert(
                title="EventSchemaVersionSkew",
                message=str(alert),
                severity="high",
                context={
                    "consumer_id": self._consumer_id,
                    "event_type": event_type,
                    "received_version": version,
                    "known_versions": sorted(known_versions_set),
                    "event_id": event_id,
                    "tenant_id": tenant_id,
                },
            )
            return

        unknown_alert = UnknownEventTypeReceived(
            consumer_id=self._consumer_id,
            event_type=event_type,
            schema_version=version,
            event_id=event_id,
            tenant_id=tenant_id,
            received_at=timestamp,
        )
        await self._alert_dispatcher.send_alert(
            title="UnknownEventTypeReceived",
            message=str(unknown_alert),
            severity="high",
            context={
                "consumer_id": self._consumer_id,
                "event_type": event_type,
                "schema_version": version,
                "event_id": event_id,
                "tenant_id": tenant_id,
            },
        )


__all__ = ["VersionAwareSubscription"]
