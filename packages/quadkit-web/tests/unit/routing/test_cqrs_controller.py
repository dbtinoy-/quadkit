"""Tests for CQRSController — command and query bus integration in controllers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.web.routing.cqrs import CQRSController


class _TestCommand:
    """Stub command for testing dispatch."""

    def __init__(self, value: str = "test") -> None:
        self.value = value


class _TestQuery:
    """Stub query for testing dispatch."""

    def __init__(self, filter_by: str = "active") -> None:
        self.filter_by = filter_by


class TestCQRSControllerInit:
    """Tests for CQRSController construction and attribute defaults."""

    def test_creates_with_no_buses(self) -> None:
        ctrl = CQRSController()
        assert ctrl._command_bus is None
        assert ctrl._query_bus is None

    def test_creates_with_command_bus_only(self) -> None:
        bus = MagicMock()
        ctrl = CQRSController(command_bus=bus)
        assert ctrl._command_bus is bus
        assert ctrl._query_bus is None

    def test_creates_with_query_bus_only(self) -> None:
        bus = MagicMock()
        ctrl = CQRSController(query_bus=bus)
        assert ctrl._command_bus is None
        assert ctrl._query_bus is bus

    def test_creates_with_both_buses(self) -> None:
        cmd_bus = MagicMock()
        qry_bus = MagicMock()
        ctrl = CQRSController(command_bus=cmd_bus, query_bus=qry_bus)
        assert ctrl._command_bus is cmd_bus
        assert ctrl._query_bus is qry_bus

    def test_is_subclass_of_controller(self) -> None:
        from quadkit.web.routing.controllers import Controller

        assert issubclass(CQRSController, Controller)

    def test_collect_routes_inherited(self) -> None:
        routes = CQRSController.collect_routes()
        assert isinstance(routes, list)


class TestDispatchCommand:
    """Tests for CQRSController.dispatch_command."""

    @pytest.mark.asyncio
    async def test_dispatches_command_to_bus(self) -> None:
        cmd_bus = MagicMock()
        cmd_bus.dispatch = AsyncMock(return_value={"id": "order-123"})
        ctrl = CQRSController(command_bus=cmd_bus)

        command = _TestCommand(value="create")
        result = await ctrl.dispatch_command(command)

        cmd_bus.dispatch.assert_awaited_once_with(command)
        assert result == {"id": "order-123"}

    @pytest.mark.asyncio
    async def test_returns_handler_result(self) -> None:
        cmd_bus = MagicMock()
        cmd_bus.dispatch = AsyncMock(return_value=42)
        ctrl = CQRSController(command_bus=cmd_bus)

        result = await ctrl.dispatch_command(_TestCommand())
        assert result == 42

    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_bus(self) -> None:
        ctrl = CQRSController()

        with pytest.raises(RuntimeError, match="no CommandBusProtocol configured"):
            await ctrl.dispatch_command(_TestCommand())

    @pytest.mark.asyncio
    async def test_propagates_handler_exception(self) -> None:
        cmd_bus = MagicMock()
        cmd_bus.dispatch = AsyncMock(side_effect=ValueError("invalid command"))
        ctrl = CQRSController(command_bus=cmd_bus)

        with pytest.raises(ValueError, match="invalid command"):
            await ctrl.dispatch_command(_TestCommand())

    @pytest.mark.asyncio
    async def test_error_message_includes_class_name(self) -> None:
        class OrderController(CQRSController):
            pass

        ctrl = OrderController()

        with pytest.raises(RuntimeError, match="OrderController"):
            await ctrl.dispatch_command(_TestCommand())


class TestDispatchQuery:
    """Tests for CQRSController.dispatch_query."""

    @pytest.mark.asyncio
    async def test_dispatches_query_to_bus(self) -> None:
        qry_bus = MagicMock()
        qry_bus.execute = AsyncMock(return_value=[{"name": "Item 1"}])
        ctrl = CQRSController(query_bus=qry_bus)

        query = _TestQuery(filter_by="active")
        result = await ctrl.dispatch_query(query)

        qry_bus.execute.assert_awaited_once_with(query)
        assert result == [{"name": "Item 1"}]

    @pytest.mark.asyncio
    async def test_returns_query_result(self) -> None:
        qry_bus = MagicMock()
        qry_bus.execute = AsyncMock(return_value=None)
        ctrl = CQRSController(query_bus=qry_bus)

        result = await ctrl.dispatch_query(_TestQuery())
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_runtime_error_without_bus(self) -> None:
        ctrl = CQRSController()

        with pytest.raises(RuntimeError, match="no QueryBusProtocol configured"):
            await ctrl.dispatch_query(_TestQuery())

    @pytest.mark.asyncio
    async def test_propagates_handler_exception(self) -> None:
        qry_bus = MagicMock()
        qry_bus.execute = AsyncMock(side_effect=LookupError("not found"))
        ctrl = CQRSController(query_bus=qry_bus)

        with pytest.raises(LookupError, match="not found"):
            await ctrl.dispatch_query(_TestQuery())

    @pytest.mark.asyncio
    async def test_error_message_includes_class_name(self) -> None:
        class ReportController(CQRSController):
            pass

        ctrl = ReportController()

        with pytest.raises(RuntimeError, match="ReportController"):
            await ctrl.dispatch_query(_TestQuery())


class TestCQRSControllerCombined:
    """Tests for CQRSController with both buses."""

    @pytest.mark.asyncio
    async def test_dispatch_command_and_query_independently(self) -> None:
        cmd_bus = MagicMock()
        cmd_bus.dispatch = AsyncMock(return_value="cmd_result")
        qry_bus = MagicMock()
        qry_bus.execute = AsyncMock(return_value="qry_result")
        ctrl = CQRSController(command_bus=cmd_bus, query_bus=qry_bus)

        cmd_result = await ctrl.dispatch_command(_TestCommand())
        qry_result = await ctrl.dispatch_query(_TestQuery())

        assert cmd_result == "cmd_result"
        assert qry_result == "qry_result"
        cmd_bus.dispatch.assert_awaited_once()
        qry_bus.execute.assert_awaited_once()
