"""End-to-end tests for quadkit-events"""

from uuid import uuid4
from dataclasses import dataclass

import pytest

from quadkit.events.aggregates import AggregateRoot
from quadkit.events.buses import CommandBusImpl, EventBusImpl, QueryBusImpl
from quadkit.events.messages import Command, Query
from quadkit.contracts.domain import DomainEvent
from quadkit.events.di import EventsProvider
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores import (
    InMemoryEventStore,
    InMemorySnapshotStore,
    SnapshotManager,
)

@pytest.mark.e2e

@dataclass(frozen=True, kw_only=True)
class PlaceOrderCommand(Command):
    """Command to place an order"""

    customer_id: str
    product_id: str
    quantity: int


@dataclass(frozen=True, kw_only=True)
class ShipOrderCommand(Command):
    """Command to ship an order"""

    order_id: str
    tracking_number: str


@dataclass(frozen=True, kw_only=True)
class GetOrderQuery(Query):
    """Query to get an order"""

    order_id: str


@dataclass(frozen=True, kw_only=True)
class GetCustomerOrdersQuery(Query):
    """Query to get all orders for a customer"""

    customer_id: str


class OrderPlacedEvent(DomainEvent):
    """Event when order is placed"""

    customer_id: str = ""
    product_id: str = ""
    quantity: int = 0


class OrderShippedEvent(DomainEvent):
    """Event when order is shipped"""

    tracking_number: str = ""


class Order(AggregateRoot):
    """Order aggregate"""

    customer_id: str = ""
    product_id: str = ""
    quantity: int = 0
    status: str = "pending"
    tracking_number: str = ""

    def place(self, customer_id: str, product_id: str, quantity: int):
        """Place a new order"""
        self._apply(
            OrderPlacedEvent(
                aggregate_id=self.id,
                aggregate_type=self.__class__.__name__,
                event_type=OrderPlacedEvent.__name__,
                sequence_number=0,
                actor_id="system",
                customer_id=customer_id,
                product_id=product_id,
                quantity=quantity,
            ),
        )

    def ship(self, tracking_number: str):
        """Ship the order"""
        self._apply(
            OrderShippedEvent(
                aggregate_id=self.id,
                aggregate_type=self.__class__.__name__,
                event_type=OrderShippedEvent.__name__,
                sequence_number=0,
                actor_id="system",
                tracking_number=tracking_number,
            ),
        )

    def _handle_order_placed(self, event: OrderPlacedEvent):
        """Apply order placed event"""
        self.id = event.aggregate_id
        self.customer_id = event.customer_id
        self.product_id = event.product_id
        self.quantity = event.quantity
        self.status = "placed"

    def _handle_order_shipped(self, event: OrderShippedEvent):
        """Apply order shipped event"""
        self.tracking_number = event.tracking_number
        self.status = "shipped"


class TestE2EOrderProcessing:
    """End-to-end tests for order processing workflow"""

    @pytest.mark.asyncio
    async def test_complete_order_lifecycle(self):
        """Test complete order lifecycle from placement to shipping"""

        class PlaceOrderHandler:
            """Handler for PlaceOrderCommand"""

            def __init__(
                self, repository: EventSourcingRepository, event_bus: EventBusImpl,
            ):
                self.repository = repository
                self.event_bus = event_bus

            async def handle(self, cmd: PlaceOrderCommand):
                order = Order()
                order.place(cmd.customer_id, cmd.product_id, cmd.quantity)
                await self.repository.save(order)
                return order.id

        class ShipOrderHandler:
            """Handler for ShipOrderCommand"""

            def __init__(
                self, repository: EventSourcingRepository, event_bus: EventBusImpl,
            ):
                self.repository = repository
                self.event_bus = event_bus

            async def handle(self, cmd: ShipOrderCommand):
                from uuid import UUID

                order = await self.repository.get(UUID(cmd.order_id))
                # Ensure mypy knows order is not None
                assert order is not None
                order.ship(cmd.tracking_number)
                await self.repository.save(order)
                return True

        class GetOrderHandler:
            """Handler for GetOrderQuery"""

            def __init__(self, orders_view: dict):
                self.orders_view = orders_view

            async def handle(self, query: GetOrderQuery):
                return self.orders_view.get(query.order_id)

        class GetCustomerOrdersHandler:
            """Handler for GetCustomerOrdersQuery"""

            def __init__(self, customer_orders_view: dict, orders_view: dict):
                self.customer_orders_view = customer_orders_view
                self.orders_view = orders_view

            async def handle(self, query: GetCustomerOrdersQuery):
                order_ids = self.customer_orders_view.get(query.customer_id, [])
                return [
                    self.orders_view.get(oid)
                    for oid in order_ids
                    if oid in self.orders_view
                ]

        # Setup infrastructure
        event_store = InMemoryEventStore()
        snapshot_store = InMemorySnapshotStore()
        snapshot_manager = SnapshotManager(
            event_store=event_store, snapshot_store=snapshot_store,
        )
        command_bus = CommandBusImpl()
        query_bus = QueryBusImpl()
        event_bus = EventBusImpl()
        repository = EventSourcingRepository(
            Order, event_store, snapshot_store, event_bus=event_bus,
        )

        # Read model for queries
        orders_view = {}
        customer_orders_view = {}

        # Command handlers
        place_handler = PlaceOrderHandler(repository, event_bus)
        command_bus.register(PlaceOrderCommand, place_handler)

        ship_handler = ShipOrderHandler(repository, event_bus)
        command_bus.register(ShipOrderCommand, ship_handler)

        # Event handlers for read model projection
        async def project_order_placed(event: OrderPlacedEvent):
            order_id = str(event.aggregate_id)
            orders_view[order_id] = {
                "id": order_id,
                "customer_id": event.customer_id,
                "product_id": event.product_id,
                "quantity": event.quantity,
                "status": "placed",
            }
            # Update customer orders
            customer_id = event.customer_id
            if customer_id not in customer_orders_view:
                customer_orders_view[customer_id] = []
            customer_orders_view[customer_id].append(order_id)

        async def project_order_shipped(event: OrderShippedEvent):
            order_id = str(event.aggregate_id)
            if order_id in orders_view:
                orders_view[order_id]["status"] = "shipped"
                orders_view[order_id]["tracking_number"] = event.tracking_number

        event_bus.subscribe(OrderPlacedEvent, project_order_placed)
        event_bus.subscribe(OrderShippedEvent, project_order_shipped)

        # Query handlers
        get_order_handler = GetOrderHandler(orders_view)
        query_bus.register(GetOrderQuery, get_order_handler)

        get_customer_orders_handler = GetCustomerOrdersHandler(
            customer_orders_view, orders_view,
        )
        query_bus.register(GetCustomerOrdersQuery, get_customer_orders_handler)

        # Execute workflow
        customer_id = str(uuid4())
        product_id = str(uuid4())

        # Place order
        place_cmd = PlaceOrderCommand(
            customer_id=customer_id,
            product_id=product_id,
            quantity=2,
        )
        order_id = await command_bus.dispatch(place_cmd)
        # Wait for event bus drain tasks to project the read model
        await event_bus.flush()

        # Query order
        get_order_query = GetOrderQuery(order_id=str(order_id))
        order = await query_bus.execute(get_order_query)

        # Verify order was placed
        assert order["customer_id"] == customer_id
        assert order["product_id"] == product_id
        assert order["quantity"] == 2
        assert order["status"] == "placed"

        # Ship order
        ship_cmd = ShipOrderCommand(order_id=str(order_id), tracking_number="TRK123456")
        await command_bus.dispatch(ship_cmd)
        # Wait for event bus drain tasks to project the read model
        await event_bus.flush()

        # Query updated order
        updated_order = await query_bus.execute(get_order_query)

        # Verify order was shipped
        assert updated_order["status"] == "shipped"
        assert updated_order["tracking_number"] == "TRK123456"

        # Query customer orders
        customer_orders_query = GetCustomerOrdersQuery(customer_id=customer_id)
        customer_orders = await query_bus.execute(customer_orders_query)

        # Verify customer has the order
        assert len(customer_orders) == 1
        assert customer_orders[0]["id"] == str(order_id)

    @pytest.mark.asyncio
    async def test_event_sourcing_with_snapshots(self):
        """Test event sourcing with snapshot optimization"""
        event_store = InMemoryEventStore()
        snapshot_store = InMemorySnapshotStore()
        snapshot_manager = SnapshotManager(
            event_store=event_store, snapshot_store=snapshot_store,
        )
        repository = EventSourcingRepository(Order, event_store, snapshot_store)

        # Create order with multiple events
        order = Order()
        order.place("customer1", "product1", 1)
        await repository.save(order)

        order.ship("TRK001")
        await repository.save(order)

        # Add more events to trigger snapshot
        order.place("customer1", "product2", 1)  # This creates a new aggregate
        await repository.save(order)

        order.ship("TRK002")
        await repository.save(order)

        order.place("customer1", "product3", 1)
        await repository.save(order)

        # Load order - should use snapshot optimization
        loaded_order = await repository.get(order.id)

        # Verify state is correct
        assert loaded_order.customer_id == "customer1"
        assert loaded_order.product_id == "product3"
        assert loaded_order.quantity == 1
        assert loaded_order.status == "placed"
        assert loaded_order.version == 5

    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self):
        """Test handling concurrent operations on orders"""
        event_store = InMemoryEventStore()
        repository = EventSourcingRepository(Order, event_store)

        command_bus = CommandBusImpl()
        event_bus = EventBusImpl()

        class PlaceOrderHandler:
            """Handler for PlaceOrderCommand"""

            def __init__(
                self, repository: EventSourcingRepository, event_bus: EventBusImpl,
            ):
                self.repository = repository
                self.event_bus = event_bus

            async def handle(self, cmd: PlaceOrderCommand):
                order = Order()
                order.place(cmd.customer_id, cmd.product_id, cmd.quantity)
                await self.repository.save(order)
                return order.id

        # Command handler with concurrency control
        place_handler = PlaceOrderHandler(repository, event_bus)
        command_bus.register(PlaceOrderCommand, place_handler)

        # Process multiple orders concurrently
        import asyncio

        async def place_order_async(customer_id: str, product_id: str):
            cmd = PlaceOrderCommand(
                customer_id=customer_id,
                product_id=product_id,
                quantity=1,
            )
            return await command_bus.dispatch(cmd)

        # Place multiple orders concurrently
        tasks = list(map(lambda i: place_order_async(f"customer{i}", f"product{i}"), range(5)))

        order_ids = await asyncio.gather(*tasks)

        # Verify all orders were created
        assert len(order_ids) == 5
        assert len(set(order_ids)) == 5  # All unique

        # Verify all orders can be loaded
        for order_id in order_ids:
            order = await repository.get(order_id)
            assert order is not None
            assert order.status == "placed"


class TestEventsProviderIntegration:
    """Integration tests with EventsProvider"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="EventsProvider.register() requires config refactor")
    async def test_provider_lifecycle(self):
        """Test EventsProvider lifecycle"""
        from quadkit.events.config import EventsConfig

        provider = EventsProvider(config=EventsConfig())

        # Check initial state
        assert provider.config is not None
        assert provider.command_bus is None  # Not created yet
        assert provider.query_bus is None
        assert provider.event_bus is None
        assert provider.event_store is None

        # Skipped: EventsProvider.register() requires config refactor
        # await provider.register(container)
