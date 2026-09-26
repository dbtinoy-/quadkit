"""Integration tests for quadkit-events"""

import pytest
from dataclasses import dataclass

from quadkit.events.aggregates import AggregateRoot
from quadkit.events.buses import CommandBusImpl, EventBusImpl, QueryBusImpl
from quadkit.events.messages import Command, Query
from quadkit.contracts.domain import DomainEvent
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores import InMemoryEventStore


@pytest.mark.integration
@dataclass(frozen=True, kw_only=True)
class CreateUserCommand(Command):
    """Command to create a user"""

    name: str
    email: str


@dataclass(frozen=True, kw_only=True)
class GetUserQuery(Query):
    """Query to get a user"""

    user_id: str


class UserCreatedEvent(DomainEvent):
    """Event when user is created"""

    name: str = ""
    email: str = ""


class User(AggregateRoot):
    """User aggregate"""

    name: str = ""
    email: str = ""

    def create(self, name: str, email: str):
        """Create a new user"""
        self._apply(
            UserCreatedEvent(
                aggregate_id=self.id,
                aggregate_type=self.__class__.__name__,
                event_type=UserCreatedEvent.__name__,
                sequence_number=0,
                actor_id="system",
                name=name,
                email=email,
            ),
        )

    def _handle_user_created(self, event: UserCreatedEvent):
        """Apply user created event"""
        self.id = event.aggregate_id
        self.name = event.name
        self.email = event.email


class TestCommandBusIntegration:
    """Integration tests for CommandBusProtocol"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_command_handler_registration_and_dispatch(self):
        """Test complete command flow"""
        bus = CommandBusImpl()
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        class CreateUserHandler:
            """Handler for CreateUserCommand"""

            def __init__(self, repo: EventSourcingRepository):
                self.repository = repo

            async def handle(self, cmd: CreateUserCommand):
                user = User()
                user.create(cmd.name, cmd.email)
                await self.repository.save(user)
                return user.id

        # Register command handler
        handler = CreateUserHandler(repository)
        bus.register(CreateUserCommand, handler)

        # Dispatch command
        cmd = CreateUserCommand(name="John Doe", email="john@example.com")
        user_id = await bus.dispatch(cmd)

        # Verify user was created
        assert user_id is not None
        user = await repository.get(user_id)
        # Ensure mypy knows user is not None
        assert user is not None
        assert user.name == "John Doe"


class TestQueryBusIntegration:
    """Integration tests for QueryBusProtocol"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_handler_registration_and_dispatch(self):
        """Test complete query flow"""
        bus = QueryBusImpl()
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        # Create a user first
        user = User()
        user.create("Jane Doe", "jane@example.com")
        await repository.save(user)

        class GetUserHandler:
            """Handler for GetUserQuery"""

            def __init__(self, repo: EventSourcingRepository):
                self.repository = repo

            async def handle(self, query: GetUserQuery):
                from uuid import UUID

                user = await self.repository.get(UUID(query.user_id))
                # Ensure mypy knows user is not None
                assert user is not None
                return {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "version": user.version,
                }

        # Register query handler
        handler = GetUserHandler(repository)
        bus.register(GetUserQuery, handler)

        # Dispatch query
        query = GetUserQuery(user_id=str(user.id))
        result = await bus.execute(query)

        # Verify result
        assert result["name"] == "Jane Doe"


class TestEventBusIntegration:
    """Integration tests for EventBusProtocol"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_event_handler_registration_and_publish(self):
        """Test complete event flow"""
        bus = EventBusImpl()
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        # Track events
        received_events = []

        # Register event handler
        async def handle_user_created(event: UserCreatedEvent):
            received_events.append(event)

        bus.subscribe(UserCreatedEvent, handle_user_created)

        # Create and save user (which publishes events)
        user = User()
        user.create("Bob Smith", "bob@example.com")

        # Get events before saving (since save clears them)
        pending_events = user.get_pending_events()
        await repository.save(user)

        # Publish events manually for this test
        for event in pending_events:
            await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        # Verify event was handled
        assert len(received_events) == 1
        event = received_events[0]
        assert event.name == "Bob Smith"
        assert event.email == "bob@example.com"


class TestEventSourcingIntegration:
    """Integration tests for EventSourcingRepository"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_event_sourcing_workflow(self):
        """Test complete event sourcing workflow"""
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        # Create user
        user = User()
        user.create("Alice Johnson", "alice@example.com")
        await repository.save(user)

        # Load user from events
        loaded_user = await repository.get(user.id)

        # Verify state
        assert loaded_user.id == user.id
        assert loaded_user.name == "Alice Johnson"
        assert loaded_user.email == "alice@example.com"
        assert loaded_user.version == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_modification(self):
        """Test concurrent modification handling"""
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        # Create user
        user = User()
        user.create("Concurrent User", "concurrent@example.com")
        await repository.save(user)

        # Load user in two different contexts
        user1 = await repository.get(user.id)
        user2 = await repository.get(user.id)

        # Both should have same version
        assert user1.version == user2.version == 1

        # Modify both (this would normally be handled by optimistic concurrency)
        # In real scenarios, the second save would fail
        user1.create("Updated Name 1", "updated1@example.com")
        user2.create("Updated Name 2", "updated2@example.com")

        # First save should succeed
        await repository.save(user1)

        # Second save should fail due to concurrency
        with pytest.raises(Exception):
            await repository.save(user2)


class TestCQRSIntegration:
    """Integration tests for CQRS pattern"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cqrs_separation(self):
        """Test command/query separation"""
        command_bus = CommandBusImpl()
        query_bus = QueryBusImpl()
        event_bus = EventBusImpl()
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(User, event_store)

        class CreateUserHandler:
            """Handler for CreateUserCommand"""

            def __init__(self, repo: EventSourcingRepository):
                self.repository = repo

            async def handle(self, cmd: CreateUserCommand):
                user = User()
                user.create(cmd.name, cmd.email)
                await self.repository.save(user)
                return user.id

        # Command side - write model
        command_handler = CreateUserHandler(repository)
        command_bus.register(CreateUserCommand, command_handler)

        # Query side - read model (simplified)
        users_view = {}  # In real app, this would be a separate read database

        async def project_user_created(event: UserCreatedEvent):
            users_view[str(event.aggregate_id)] = {
                "name": event.name,
                "email": event.email,
            }

        event_bus.subscribe(UserCreatedEvent, project_user_created)

        class GetUserHandler:
            """Handler for GetUserQuery"""

            def __init__(self, repo: EventSourcingRepository):
                self.repository = repo

            async def handle(self, query: GetUserQuery):
                from uuid import UUID

                user = await self.repository.get(UUID(query.user_id))
                # Ensure mypy knows user is not None
                assert user is not None
                return {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "version": user.version,
                }

        query_handler = GetUserHandler(repository)
        query_bus.register(GetUserQuery, query_handler)

        # Execute command
        cmd = CreateUserCommand(name="CQRS User", email="cqrs@example.com")
        user_id = await command_bus.dispatch(cmd)

        # Query the read model
        query = GetUserQuery(user_id=str(user_id))
        result = await query_bus.execute(query)

        # Verify CQRS separation worked
        assert result["name"] == "CQRS User"
        assert result["email"] == "cqrs@example.com"
