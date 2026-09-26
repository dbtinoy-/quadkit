"""Browser-facing scenario built on Quadkit Events public contracts."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from quadkit.contracts.events import (
    EventBusDiagnosticsProtocol,
    EventBusProtocol,
    EventReplayProtocol,
    EventStoreProtocol,
)
from quadkit.result import Result
from timeline_lab.config import TimelineLabConfig
from timeline_lab.events import TimelineEvent


class TimelineService:
    """Coordinate a single in-memory stream without replacing package APIs."""

    _ACTIONS = {
        "open": "Checkout opened",
        "approve": "Checkout approved",
        "fail": "Failure probe requested",
    }

    def __init__(
        self,
        event_bus: EventBusProtocol,
        event_store: EventStoreProtocol,
        config: TimelineLabConfig,
    ) -> None:
        self._event_bus = event_bus
        self._event_store = event_store
        self._config = config
        self._deliveries: list[dict[str, Any]] = []
        self._failure_attempts: dict[str, int] = defaultdict(int)
        self._last_replay: dict[str, Any] = {
            "count": 0,
            "event_ids": [],
            "order": [],
        }

    @property
    def stream_id(self) -> str:
        """Return the configured stream shown in the browser."""
        return self._config.stream_id

    async def publish(
        self, action: str, note: str = "", actor: str = ""
    ) -> dict[str, Any]:
        """Append one event, publish it, and drain the bus for the UI response."""
        normalized = action.strip().lower()
        if normalized not in self._ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        history = await self._event_store.read(self.stream_id)
        event = TimelineEvent(
            action=normalized,
            note=note.strip()[:160],
            actor_id=(actor.strip() or self._config.default_actor)[:80],
            aggregate_id=UUID("00000000-0000-0000-0000-000000000042"),
            aggregate_type="checkout",
            version=len(history) + 1,
            stream_id=self.stream_id,
            event_id=uuid4(),
        )
        version = await self._event_store.append(
            stream_id=self.stream_id,
            events=[event],
            expected_version=len(history),
        )

        # Read back the store-owned event so the assigned global sequence is
        # visible both to the subscriber and to the browser timeline.
        stored_event = (await self._event_store.read(self.stream_id))[-1]
        result = await self._event_bus.publish(stored_event)
        # EventBusProtocol deliberately only promises enqueue semantics;
        # EventBusImpl adds flush() for deterministic tests and this lab.
        flush = getattr(self._event_bus, "flush", None)
        if flush is not None:
            await flush()

        return {
            "ok": result.is_ok(),
            "result": self._publish_result(result),
            "stream_version": version,
            "event": self._serialize(stored_event),
            "handler_failures": self._failures_for(stored_event),
            "bus_dispatch_error_count": self._bus_dispatch_error_count(),
        }

    async def history(self) -> dict[str, Any]:
        """Read the stream through EventStoreProtocol and return timeline data."""
        events = await self._event_store.read(self.stream_id)
        return self._snapshot(events)

    async def replay(self) -> dict[str, Any]:
        """Replay history via the package's public EventStore replay contract."""
        replayed: list[dict[str, Any]] = []

        async def capture(event: TimelineEvent) -> None:
            replayed.append(self._serialize(event))

        if not isinstance(self._event_store, EventReplayProtocol):
            self._last_replay = {
                "count": 0,
                "event_ids": [],
                "order": [],
                "error": "This event-store backend does not expose replay_events()",
            }
            current = await self.history()
            current["replay"] = dict(self._last_replay)
            return current

        count = await self._event_store.replay_events(
            capture,
            event_types=[TimelineEvent.__name__],
        )
        self._last_replay = {
            "count": count,
            "event_ids": [item["event_id"] for item in replayed],
            "order": [item["sequence_number"] for item in replayed],
        }
        current = await self.history()
        current["replay"] = dict(self._last_replay)
        return current

    async def health(self) -> dict[str, Any]:
        """Return readiness details for the offline event composition."""
        current = await self._event_store.read(self.stream_id)
        components = {
            "event_store": await self._component_health(self._event_store),
            "event_bus": await self._component_health(self._event_bus),
        }
        healthy = all(
            details.get("status") in {"healthy", "ok"}
            for details in components.values()
        )
        return {
            "status": "ok" if healthy else "degraded",
            "service": "events-timeline",
            "offline": True,
            "event_store": type(self._event_store).__name__,
            "event_bus": type(self._event_bus).__name__,
            "stream_id": self.stream_id,
            "event_count": len(current),
            "components": components,
        }

    @staticmethod
    async def _component_health(component: object) -> dict[str, Any]:
        """Adapt the optional HealthCheckProtocol to the lab's JSON contract."""
        check = getattr(component, "health_check", None)
        if check is None:
            return {"status": "unknown"}
        result = await check()
        to_dict = getattr(result, "to_dict", None)
        return to_dict() if to_dict is not None else {"status": str(result)}

    def _snapshot(self, events: list[TimelineEvent]) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "event_count": len(events),
            "events": [self._serialize(event) for event in events],
            "deliveries": list(self._deliveries),
            "handler_failures": [
                self._failure_entry(event_id, attempts)
                for event_id, attempts in self._failure_attempts.items()
            ],
            "bus_dispatch_error_count": self._bus_dispatch_error_count(),
            "replay": dict(self._last_replay),
            "contract": {
                "store": "EventStoreProtocol.read + append + EventReplayProtocol.replay_events",
                "bus": "EventBusProtocol.publish + subscribe; concrete flush",
            },
        }

    def _serialize(self, event: TimelineEvent) -> dict[str, Any]:
        data = event.to_dict()
        occurred_at = data.get("occurred_at")
        if isinstance(occurred_at, datetime):
            data["occurred_at"] = occurred_at.isoformat()
        data["stream_id"] = getattr(event, "stream_id", self.stream_id)
        data["label"] = self._ACTIONS.get(event.action, event.action)
        data["delivery_status"] = (
            "failed handler"
            if str(event.event_id) in self._failure_attempts
            else "handled"
        )
        return data

    @staticmethod
    def _publish_result(result: Result[Any, Any]) -> dict[str, Any]:
        """Expose the bus result without coupling the UI to Result internals."""
        if result.is_ok():
            return {
                "status": "enqueued",
                "handler_errors_are_reported_after_flush": True,
            }
        return {"status": "rejected", "error": str(result.unwrap_err())}

    def record_delivery(self, event: TimelineEvent) -> None:
        """Subscriber callback used by the event bus."""
        self._deliveries.append(
            {
                "event_id": str(event.event_id),
                "sequence_number": event.sequence_number,
                "action": event.action,
                "status": "handled",
            }
        )

    async def failure_probe(self, event: TimelineEvent) -> None:
        """A deliberate failing subscriber to make retry/error behavior visible."""
        if event.action != "fail":
            return
        event_id = str(event.event_id)
        self._failure_attempts[event_id] += 1
        raise RuntimeError("intentional lab failure; bus should retry and continue")

    def _failures_for(self, event: TimelineEvent) -> list[dict[str, Any]]:
        event_id = str(event.event_id)
        attempts = self._failure_attempts.get(event_id, 0)
        return [self._failure_entry(event_id, attempts)] if attempts else []

    def _bus_dispatch_error_count(self) -> int:
        """Read the event bus's public asynchronous diagnostics snapshot."""
        if not isinstance(self._event_bus, EventBusDiagnosticsProtocol):
            return 0
        return len(self._event_bus.dispatch_errors)

    @staticmethod
    def _failure_entry(event_id: str, attempts: int) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "attempts": attempts,
            "status": "failed",
            "message": "intentional lab failure; bus continued after retries",
        }


__all__ = ["TimelineService"]
