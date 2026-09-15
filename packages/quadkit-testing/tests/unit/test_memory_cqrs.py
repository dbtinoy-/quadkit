"""Tests for the in-memory CQRS buses, exceptions, DI provider, exports."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.audit import AuditLoggerProtocol
from quadkit.contracts.events import (
    CommandBusProtocol,
    DomainEventPublisherProtocol,
    EventBusProtocol,
    QueryBusProtocol,
)
from quadkit.contracts.exceptions.events import (
    DuplicateHandlerError as ContractDuplicateHandlerError,
)
from quadkit.contracts.exceptions.events import EventError, HandlerNotFoundError
from quadkit.result import Err, Ok
from quadkit.testing.memory.cqrs import InMemoryCommandBus, InMemoryQueryBus
from quadkit.testing.memory.di.provider import MemoryProvider
from quadkit.testing.memory.exceptions import (
    CommandBusError,
    CommandError,
    CommandHandlerNotFoundError,
    DuplicateHandlerError,
    MemoryBackendError,
    QueryBusError,
    QueryDuplicateHandlerError,
    QueryHandlerNotFoundError,
)


class CreateOrder:
    pass


class GetOrder:
    pass


class UnregisteredCommand:
    pass


class _Handler:
    def __init__(self, result: Any) -> None:
        self.result = result

    async def handle(self, command: Any) -> Any:
        return self.result


class TestInMemoryCommandBus:
    @pytest.mark.asyncio
    async def test_dispatch_to_object_handler(self) -> None:
        bus = InMemoryCommandBus()
        bus.register(CreateOrder, _Handler("created"))
        assert await bus.dispatch(CreateOrder()) == "created"

    @pytest.mark.asyncio
    async def test_dispatch_to_callable_handler(self) -> None:
        bus = InMemoryCommandBus()

        async def handler(command: Any) -> str:
            return "ok"

        bus.register(CreateOrder, handler)
        assert await bus.dispatch(CreateOrder()) == "ok"

    @pytest.mark.asyncio
    async def test_dispatch_unregistered_raises(self) -> None:
        bus = InMemoryCommandBus()
        with pytest.raises(CommandHandlerNotFoundError) as excinfo:
            await bus.dispatch(UnregisteredCommand())
        assert excinfo.value.command_type == "UnregisteredCommand"
        assert "UnregisteredCommand" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_register_unregister_has_handler_count(self) -> None:
        bus = InMemoryCommandBus()
        assert bus.handler_count == 0
        assert bus.has_handler(CreateOrder) is False
        bus.register(CreateOrder, _Handler("x"))
        assert bus.handler_count == 1
        assert bus.has_handler(CreateOrder) is True
        bus.unregister(CreateOrder)
        assert bus.handler_count == 0

    @pytest.mark.asyncio
    async def test_duplicate_registration_raises(self) -> None:
        bus = InMemoryCommandBus()
        bus.register(CreateOrder, _Handler("x"))
        with pytest.raises(DuplicateHandlerError) as excinfo:
            bus.register(CreateOrder, _Handler("y"))
        assert excinfo.value.command_type == "CreateOrder"

    @pytest.mark.asyncio
    async def test_unregister_unregistered_raises(self) -> None:
        bus = InMemoryCommandBus()
        with pytest.raises(CommandHandlerNotFoundError):
            bus.unregister(CreateOrder)

    @pytest.mark.asyncio
    async def test_middleware_wraps_dispatch(self) -> None:
        bus = InMemoryCommandBus()
        bus.register(CreateOrder, _Handler("result"))
        log: list[str] = []

        async def mw(command: Any, nxt: Any) -> Any:
            log.append("before")
            result = await nxt(command)
            log.append("after")
            return result

        bus.add_middleware(mw)
        assert await bus.dispatch(CreateOrder()) == "result"
        assert log == ["before", "after"]

    @pytest.mark.asyncio
    async def test_on_handler_error_swallows_and_returns_none(self) -> None:
        reported: list[Exception] = []
        bus = InMemoryCommandBus(
            on_handler_error=lambda _cmd, _handler, exc: reported.append(exc)
        )

        async def broken(command: Any) -> None:
            raise ValueError("boom")

        bus.register(CreateOrder, broken)
        assert await bus.dispatch(CreateOrder()) is None
        assert len(reported) == 1

    @pytest.mark.asyncio
    async def test_dispatch_result_ok_and_err_paths(self) -> None:
        bus = InMemoryCommandBus()
        bus.register(CreateOrder, _Handler(42))
        result = await bus.dispatch_result(CreateOrder())
        assert isinstance(result, Ok)
        assert result.unwrap() == 42

        missing = await bus.dispatch_result(UnregisteredCommand())
        assert isinstance(missing, Err)
        assert isinstance(missing.unwrap_err(), CommandHandlerNotFoundError)

    @pytest.mark.asyncio
    async def test_dispatch_result_wraps_handler_exception(self) -> None:
        bus = InMemoryCommandBus()

        async def broken(command: Any) -> None:
            raise KeyError("kaboom")

        bus.register(CreateOrder, broken)
        result = await bus.dispatch_result(CreateOrder())
        assert isinstance(result, Err)
        err = result.unwrap_err()
        assert isinstance(err, CommandError)
        assert isinstance(err.cause, KeyError)


class TestInMemoryQueryBus:
    @pytest.mark.asyncio
    async def test_execute_to_handler(self) -> None:
        bus = InMemoryQueryBus()
        bus.register(GetOrder, _Handler({"id": "1"}))
        assert await bus.execute(GetOrder()) == {"id": "1"}

    @pytest.mark.asyncio
    async def test_execute_unregistered_raises(self) -> None:
        bus = InMemoryQueryBus()
        with pytest.raises(QueryHandlerNotFoundError) as excinfo:
            await bus.execute(UnregisteredCommand())
        assert excinfo.value.query_type == "UnregisteredCommand"

    @pytest.mark.asyncio
    async def test_register_unregister_lifecycle(self) -> None:
        bus = InMemoryQueryBus()
        assert bus.handler_count == 0
        bus.register(GetOrder, _Handler("x"))
        assert bus.has_handler(GetOrder) is True
        with pytest.raises(QueryDuplicateHandlerError):
            bus.register(GetOrder, _Handler("y"))
        bus.unregister(GetOrder)
        assert bus.has_handler(GetOrder) is False

    @pytest.mark.asyncio
    async def test_unregister_unregistered_raises(self) -> None:
        bus = InMemoryQueryBus()
        with pytest.raises(QueryHandlerNotFoundError):
            bus.unregister(GetOrder)

    @pytest.mark.asyncio
    async def test_on_handler_error_swallows_and_returns_none(self) -> None:
        reported: list[Exception] = []
        bus = InMemoryQueryBus(
            on_handler_error=lambda _q, _h, exc: reported.append(exc)
        )

        async def broken(query: Any) -> None:
            raise ValueError("boom")

        bus.register(GetOrder, broken)
        assert await bus.execute(GetOrder()) is None
        assert len(reported) == 1

    @pytest.mark.asyncio
    async def test_execute_result_preserves_exception_type(self) -> None:
        bus = InMemoryQueryBus()

        async def broken(query: Any) -> None:
            raise ValueError("nope")

        bus.register(GetOrder, broken)
        result = await bus.execute_result(GetOrder())
        assert isinstance(result, Err)
        assert isinstance(result.unwrap_err(), ValueError)

    @pytest.mark.asyncio
    async def test_execute_result_ok(self) -> None:
        bus = InMemoryQueryBus()
        bus.register(GetOrder, _Handler("fine"))
        result = await bus.execute_result(GetOrder())
        assert isinstance(result, Ok)
        assert result.unwrap() == "fine"

    @pytest.mark.asyncio
    async def test_middleware_wraps_execute(self) -> None:
        bus = InMemoryQueryBus()
        bus.register(GetOrder, _Handler("result"))
        log: list[str] = []

        async def mw(query: Any, nxt: Any) -> Any:
            log.append("before")
            result = await nxt(query)
            log.append("after")
            return result

        bus.add_middleware(mw)
        assert await bus.execute(GetOrder()) == "result"
        assert log == ["before", "after"]


class TestMemoryExceptions:
    def test_hierarchy_and_codes(self) -> None:
        assert issubclass(MemoryBackendError, Exception)
        assert MemoryBackendError._code == "QK_ERR_TEST_003"
        assert issubclass(CommandBusError, EventError)
        assert CommandBusError._code == "QK_ERR_TEST_004"
        assert issubclass(QueryBusError, EventError)
        assert QueryBusError._code == "QK_ERR_TEST_008"

    def test_default_messages(self) -> None:
        assert "Command bus error" in str(CommandBusError())
        assert "Query bus error" in str(QueryBusError())

    def test_not_found_exceptions_carry_type(self) -> None:
        cmd = CommandHandlerNotFoundError("CreateOrder")
        assert cmd.command_type == "CreateOrder"
        assert "CreateOrder" in str(cmd)
        qry = QueryHandlerNotFoundError("GetOrder")
        assert qry.query_type == "GetOrder"
        assert "GetOrder" in str(qry)

    def test_duplicate_handler_exceptions_carry_type(self) -> None:
        cmd = DuplicateHandlerError("CreateOrder")
        assert cmd.command_type == "CreateOrder"
        qry = QueryDuplicateHandlerError("GetOrder")
        assert qry.query_type == "GetOrder"

    def test_command_error_wraps_cause(self) -> None:
        cause = KeyError("boom")
        err = CommandError(cause)
        assert err.cause is cause
        assert "boom" in str(err)

    def test_mro_membership(self) -> None:
        assert isinstance(CommandHandlerNotFoundError("X"), HandlerNotFoundError)
        assert isinstance(DuplicateHandlerError("X"), ContractDuplicateHandlerError)
        assert isinstance(CommandError(ValueError()), CommandBusError)


class _FakeContainer:
    """Records registrations; satisfies the registrar/resolver protocols."""

    def __init__(self) -> None:
        self.singletons: dict[type, Any] = {}

    def transient(
        self, service_type: type, factory: Any, validate: bool = True
    ) -> None:
        raise NotImplementedError

    def singleton(
        self,
        service_type: type,
        instance: Any = None,
        **kwargs: Any,
    ) -> None:
        self.singletons[service_type] = instance

    def resolve(self, service_type: type) -> Any:
        return self.singletons[service_type]


class TestMemoryProvider:
    @pytest.mark.asyncio
    async def test_registers_all_memory_singletons(self) -> None:
        container = _FakeContainer()
        provider = MemoryProvider()
        assert provider.name == "memory"
        await provider.register(container)

        bus = container.singletons[EventBusProtocol]
        assert isinstance(bus, EventBusProtocol)
        assert container.singletons[DomainEventPublisherProtocol] is bus
        assert isinstance(container.singletons[CommandBusProtocol], InMemoryCommandBus)
        assert isinstance(container.singletons[QueryBusProtocol], InMemoryQueryBus)
        assert isinstance(
            container.singletons[AuditLoggerProtocol], AuditLoggerProtocol
        )

    @pytest.mark.asyncio
    async def test_boot_and_shutdown_are_noops(self) -> None:
        provider = MemoryProvider()
        assert await provider.boot(_FakeContainer()) is None
        assert await provider.shutdown() is None


class TestMemoryPackageExports:
    def test_lazy_exports_resolve(self) -> None:
        from quadkit.testing import memory

        expected = [
            "InMemoryBlobStore",
            "FileInfo",
            "InMemoryCacheBackend",
            "InMemoryAuditLogger",
            "InMemoryCommandBus",
            "InMemoryQueryBus",
            "InMemoryEventBus",
            "InMemoryAsyncLock",
            "InMemoryDistributedLock",
            "InMemoryLockStore",
            "InMemoryOutbox",
            "OutboxEntry",
            "OutboxRelay",
            "OutboxStatus",
            "InMemoryRepository",
            "InMemoryUnitOfWork",
            "MemoryConfig",
            "MemoryBackendError",
            "MemoryProvider",
            "CommandBusError",
            "CommandError",
            "CommandHandlerNotFoundError",
            "DuplicateHandlerError",
            "QueryBusError",
            "QueryDuplicateHandlerError",
            "QueryHandlerNotFoundError",
            "DEFAULT_AUDIT_CAPACITY",
            "DEFAULT_EVENT_BUS_CAPACITY",
            "DEFAULT_OUTBOX_CAPACITY",
            "DEFAULT_REPOSITORY_CAPACITY",
        ]
        for name in expected:
            assert name in memory.__all__
            assert name in dir(memory)
            assert getattr(memory, name) is not None

    def test_unknown_attribute_raises(self) -> None:
        from quadkit.testing import memory

        # Exercise the module's lazy __getattr__ directly.
        with pytest.raises(AttributeError, match="no_such_thing"):
            memory.__getattr__("no_such_thing")

    def test_capacity_constants(self) -> None:
        from quadkit.testing.memory import constants

        assert constants.ENV_PREFIX == "QK_MEMORY_"
        assert constants.DEFAULT_REPOSITORY_CAPACITY == 10_000
        assert constants.DEFAULT_EVENT_BUS_CAPACITY == 1_000
        assert constants.DEFAULT_OUTBOX_CAPACITY == 5_000
        assert constants.DEFAULT_AUDIT_CAPACITY == 10_000
