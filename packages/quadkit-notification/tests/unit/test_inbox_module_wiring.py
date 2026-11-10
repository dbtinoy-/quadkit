"""Tests for the inbox module, provider, and service settings.

`InboxService`, `DatabaseInboxStore` and `InboxConfig` all shipped with no
provider, so the framework inbox was unreachable through DI — which is why
applications kept private notification tables instead. These tests pin the
wiring: the store follows the container (database when one is bound, memory
otherwise), the service and the store are the same instance for every caller,
and the config settings do something.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.contracts.notification.inbox import InboxStoreProtocol
from quadkit.notification.config import InboxConfig
from quadkit.notification.di.inbox_provider import InboxProvider
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.memory import InMemoryInboxStore
from quadkit.notification.inbox.module import InboxModule
from quadkit.notification.inbox.service import InboxService


class _Container:
    """Minimal container double: records bindings and resolves them back.

    One object plays registrar and resolver, which is what the provider's
    factories receive in production too — the container hands itself to the
    factory it is about to store.
    """

    def __init__(self, db: Any = None) -> None:
        self.entries: dict[Any, Any] = {}
        self._instances: dict[Any, Any] = {}
        self._db = db

    def singleton(
        self, service_type: Any, factory: Any = None, *, name: Any = None
    ) -> None:
        self.entries[service_type] = factory

    def has(self, service_type: Any) -> bool:
        if service_type is DatabaseProviderProtocol:
            return self._db is not None
        return service_type in self.entries

    def can_resolve(self, service_type: Any) -> bool:
        return self.has(service_type)

    async def resolve(self, service_type: Any) -> Any:
        if service_type is DatabaseProviderProtocol:
            if self._db is None:
                raise LookupError(service_type)
            return self._db
        return await self.build(service_type)

    async def resolve_optional(self, service_type: Any) -> Any:
        return await self.resolve(service_type) if self.has(service_type) else None

    async def build(self, service_type: Any) -> Any:
        """Resolve a recorded binding the way the container would.

        Three shapes reach a container: an already-built instance, a class the
        container constructs, and a factory the container calls with itself.
        The result is memoised because every binding under test is a singleton —
        the identity of that instance is part of what is asserted, and a
        per-call double would hide a provider that registered a transient where
        one store is required.
        """
        import inspect

        if service_type in self._instances:
            return self._instances[service_type]
        entry = self.entries[service_type]
        if inspect.isclass(entry):
            instance = entry()
        elif callable(entry):
            result = entry(self)
            instance = await result if inspect.isawaitable(result) else result
        else:
            instance = entry
        self._instances[service_type] = instance
        return instance


#: Stand-in database provider; the tests assert on its identity, nothing else.
db_sentinel = object()


class TestInboxProvider:
    @pytest.mark.asyncio
    async def test_store_is_database_backed_when_a_provider_is_bound(self) -> None:
        registrar = _Container(db_sentinel)
        await InboxProvider(config=InboxConfig()).register(registrar)

        store = await registrar.build(InboxStoreProtocol)

        assert isinstance(store, DatabaseInboxStore)
        assert store._db is db_sentinel

    @pytest.mark.asyncio
    async def test_database_backend_without_a_database_provider_fails_loudly(
        self,
    ) -> None:
        """A silent in-memory fallback would drop every message on restart.

        The default backend is ``database``, so an application that forgets to
        register a database provider gets an error — not an inbox that looks
        empty over an API and loses writes on the next deploy.
        """
        registrar = _Container()
        await InboxProvider(config=InboxConfig()).register(registrar)

        with pytest.raises(LookupError):
            await registrar.build(InboxStoreProtocol)

    @pytest.mark.asyncio
    async def test_memory_backend_can_be_forced_by_config(self) -> None:
        registrar = _Container()
        await InboxProvider(config=InboxConfig(store_backend="memory")).register(
            registrar
        )

        assert isinstance(await registrar.build(InboxStoreProtocol), InMemoryInboxStore)

    @pytest.mark.asyncio
    async def test_unknown_backend_does_not_silently_lose_data(self) -> None:
        registrar = _Container()
        with pytest.raises(ValueError, match="store_backend"):
            await InboxProvider(config=InboxConfig(store_backend="databse")).register(
                registrar
            )

    @pytest.mark.asyncio
    async def test_service_uses_the_bound_store(self) -> None:
        registrar = _Container(db_sentinel)
        await InboxProvider(config=InboxConfig()).register(registrar)

        service = await registrar.build(InboxService)

        assert isinstance(service, InboxService)
        assert isinstance(service._store, DatabaseInboxStore)
        assert service._store is await registrar.build(InboxStoreProtocol)

    @pytest.mark.asyncio
    async def test_service_carries_the_config_the_store_was_built_with(self) -> None:
        """A second default `InboxConfig` would silently ignore the settings."""
        registrar = _Container(db_sentinel)
        config = InboxConfig(max_page_size=7, mark_read_on_fetch=True)
        await InboxProvider(config=config).register(registrar)

        assert await registrar.build(InboxConfig) is config
        assert (await registrar.build(InboxService))._config is config

    @pytest.mark.asyncio
    async def test_module_exports_the_service_and_the_store(self) -> None:
        descriptor = InboxModule.configure(InboxConfig())
        assert descriptor.exports == [InboxService, InboxStoreProtocol]
        assert isinstance(descriptor.providers[0], InboxProvider)

    @pytest.mark.asyncio
    async def test_stub_module_never_touches_a_database(self) -> None:
        descriptor = InboxModule.stub()
        registrar = _Container()
        await descriptor.providers[0].register(registrar)

        assert isinstance(await registrar.build(InboxStoreProtocol), InMemoryInboxStore)


class TestInboxServiceSettings:
    @pytest.mark.asyncio
    async def test_page_size_ceiling_is_enforced(self) -> None:
        service = InboxService(
            InMemoryInboxStore(), config=InboxConfig(max_page_size=2)
        )
        for index in range(5):
            await service.send(user_id="u1", title=f"t{index}", body="b")

        assert len(await service.get_inbox("u1")) == 2
        assert len(await service.get_inbox("u1", limit=4)) == 2

        # An explicit smaller page is honoured; the ceiling is a maximum.
        assert len(await service.get_inbox("u1", limit=1)) == 1

    @pytest.mark.asyncio
    async def test_offset_walks_pages_without_duplicates(self) -> None:
        service = InboxService(InMemoryInboxStore())
        for index in range(4):
            await service.send(user_id="u1", title=f"t{index}", body="b")

        first = await service.get_inbox("u1", limit=2, offset=0)
        second = await service.get_inbox("u1", limit=2, offset=2)

        assert {m.id for m in first}.isdisjoint({m.id for m in second})
        assert len(first) == len(second) == 2

    @pytest.mark.asyncio
    async def test_negative_offset_is_rejected(self) -> None:
        service = InboxService(InMemoryInboxStore())
        with pytest.raises(ValueError, match="offset"):
            await service.get_inbox("u1", offset=-1)

    @pytest.mark.asyncio
    async def test_mark_read_on_fetch_marks_and_reports_read(self) -> None:
        service = InboxService(
            InMemoryInboxStore(), config=InboxConfig(mark_read_on_fetch=True)
        )
        await service.send(user_id="u1", title="t", body="b")

        [message] = await service.get_inbox("u1")

        assert message.read is True
        assert await service.count_unread("u1") == 0

    @pytest.mark.asyncio
    async def test_count_reports_the_whole_inbox_not_the_page(self) -> None:
        service = InboxService(
            InMemoryInboxStore(), config=InboxConfig(max_page_size=2)
        )
        for index in range(5):
            await service.send(user_id="u1", title=f"t{index}", body="b")
        await service.send(user_id="u2", title="theirs", body="b")

        assert await service.count("u1") == 5
        assert await service.count("u1", unread_only=True) == 5
        assert await service.count("u2") == 1
