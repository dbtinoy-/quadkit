"""Event/snapshot store, repository, aggregate, projection protocols."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.events.protocols import (
    AggregateFactoryProtocol,
    CommandBusProtocol,
    CommandHandlerProtocol,
    DomainEventPublisherProtocol,
    EventBusProtocol,
    EventHandlerProtocol,
    EventMiddlewareProtocol,
    EventReplayProtocol,
    EventSourcedReadRepositoryProtocol,
    EventSourcedRepositoryProtocol,
    EventStoreProtocol,
    IntegrationEventProtocol,
    MultiEventHandlerProtocol,
    ProjectionProtocol,
    PubSubProtocol,
    QueryBusProtocol,
    QueryHandlerProtocol,
    SnapshotStoreProtocol,
    WebhookSignatureVerifierProtocol,
)


class TestEventStoreProtocol:
    """Tests for EventStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_append_method(self) -> None:
        """Test protocol has append async method."""

        class Store:
            async def append(
                self,
                stream_id: str,
                events: list[Any],
                expected_version: int | None = None,
            ) -> int:
                return 1

        store = Store()
        version = await store.append("stream-1", [{"event": "test"}])
        assert version == 1

    @pytest.mark.asyncio
    async def test_has_read_method(self) -> None:
        """Test protocol has read async method."""

        class Store:
            async def read(
                self,
                stream_id: str,
                start: int = 0,
                count: int | None = None,
            ) -> list[Any]:
                return [{"event": "test"}]

        store = Store()
        events = await store.read("stream-1")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_has_read_all_method(self) -> None:
        """Test protocol has read_all async method."""

        class Store:
            async def read_all(
                self,
                position: int = 0,
                count: int | None = None,
            ) -> list[Any]:
                return []

        store = Store()
        events = await store.read_all()
        assert isinstance(events, list)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Store:
            async def append(self, stream_id: str, events: list, **kwargs: Any) -> int:
                return 0

            async def read(self, stream_id: str, **kwargs: Any) -> list:
                return []

            async def read_all(self, **kwargs: Any) -> list:
                return []

        assert isinstance(Store(), EventStoreProtocol)


class TestEventReplayProtocol:
    """Tests for the optional replay capability."""

    def test_is_runtime_checkable_without_expanding_event_store(self) -> None:
        """Replay-capable stores can advertise replay independently."""

        class ReplayStore:
            async def replay_events(
                self,
                handler: Any,
                since: Any = None,
                event_types: list[str] | None = None,
                on_progress: Any = None,
            ) -> int:
                return 0

        assert isinstance(ReplayStore(), EventReplayProtocol)


class TestSnapshotStoreProtocol:
    """Tests for SnapshotStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_save_method(self) -> None:
        """Test protocol has save async method."""

        class Store:
            async def save(
                self, aggregate_id: str, snapshot: Any, version: int
            ) -> None:
                pass

        store = Store()
        await store.save("agg-1", {"state": "test"}, 1)

    @pytest.mark.asyncio
    async def test_has_load_method(self) -> None:
        """Test protocol has load async method."""

        class Store:
            async def load(self, aggregate_id: str) -> tuple[Any, int] | None:
                return ({"state": "test"}, 1)

        store = Store()
        result = await store.load("agg-1")
        assert result is not None

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Store:
            async def save(
                self, aggregate_id: str, snapshot: Any, version: int
            ) -> None:
                pass

            async def load(self, aggregate_id: str) -> tuple | None:
                return None

        assert isinstance(Store(), SnapshotStoreProtocol)


class TestEventSourcedReadRepositoryProtocol:
    """Tests for EventSourcedReadRepositoryProtocol."""

    @pytest.mark.asyncio
    async def test_has_get_method(self) -> None:
        """Test protocol has get async method."""

        class Repo:
            async def get(self, aggregate_id: Any) -> Any | None:
                return {"id": aggregate_id}

        repo = Repo()
        result = await repo.get("agg-1")
        assert result["id"] == "agg-1"

    @pytest.mark.asyncio
    async def test_has_exists_method(self) -> None:
        """Test protocol has exists async method."""

        class Repo:
            async def exists(self, aggregate_id: Any) -> bool:
                return True

        repo = Repo()
        result = await repo.exists("agg-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_get_all_method(self) -> None:
        """Test protocol has get_all async method."""

        class Repo:
            async def get_all(
                self,
                limit: int | None = None,
                offset: int | None = None,
            ) -> list[Any]:
                return []

        repo = Repo()
        result = await repo.get_all()
        assert isinstance(result, list)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Repo:
            async def get(self, aggregate_id: Any) -> Any | None:
                return None

            async def exists(self, aggregate_id: Any) -> bool:
                return False

            async def get_all(self, **kwargs: Any) -> list:
                return []

        assert isinstance(Repo(), EventSourcedReadRepositoryProtocol)


class TestEventSourcedRepositoryProtocol:
    """Tests for EventSourcedRepositoryProtocol."""

    def test_protocol_extends_read_repo(self) -> None:
        """Test protocol extends EventSourcedReadRepositoryProtocol."""
        assert issubclass(
            EventSourcedRepositoryProtocol, EventSourcedReadRepositoryProtocol
        )


class TestAggregateFactoryProtocol:
    """Tests for AggregateFactoryProtocol."""

    def test_factory_returns_aggregate(self) -> None:
        class Factory:
            def create(self, aggregate_id: UUID | str) -> Any:
                return "aggregate"

        assert isinstance(Factory(), AggregateFactoryProtocol)


class TestProjectionProtocol:
    """Tests for ProjectionProtocol."""

    def test_has_apply_method(self) -> None:
        """Test protocol has apply method."""

        class Projection:
            def apply(self, event: Any) -> None:
                pass

        projection = Projection()
        projection.apply({"event": "test"})

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Projection:
            def apply(self, event: Any) -> None:
                pass

        assert isinstance(Projection(), ProjectionProtocol)


class TestPubSubProtocol:
    """Tests for PubSubProtocol."""

    @pytest.mark.asyncio
    async def test_has_publish_method(self) -> None:
        """Test protocol has publish async method."""

        class PubSub:
            async def publish(self, topic: str, data: Any) -> None:
                pass

        pubsub = PubSub()
        await pubsub.publish("topic1", {"data": "test"})

    @pytest.mark.asyncio
    async def test_has_subscribe_method(self) -> None:
        """Test protocol has subscribe async method."""

        class PubSub:
            async def subscribe(
                self,
                topic: str,
                handler: Any,
            ) -> None:
                pass

        pubsub = PubSub()
        await pubsub.subscribe("topic1", lambda: None)

    @pytest.mark.asyncio
    async def test_has_unsubscribe_method(self) -> None:
        """Test protocol has unsubscribe async method."""

        class PubSub:
            async def unsubscribe(self, topic: str, handler: Any) -> None:
                pass

        pubsub = PubSub()
        await pubsub.unsubscribe("topic1", lambda: None)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class PubSub:
            async def publish(self, topic: str, data: Any) -> None:
                pass

            async def subscribe(self, topic: str, handler: Any) -> None:
                pass

            async def unsubscribe(self, topic: str, handler: Any) -> None:
                pass

        assert isinstance(PubSub(), PubSubProtocol)
