"""The SQL adapter, not Events, certifies its own supported execution machinery."""

from types import SimpleNamespace

import pytest

from quadkit.contracts.data.sql.committed_reads import (
    CommittedReadGuardProtocol,
    CommittedReadState,
)
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.database_service import DatabaseService
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("facade", [False, True])
async def test_actual_connection_transaction_and_recovery(
    pooled: bool, facade: bool
) -> None:
    pool = SQLiteConnectionPool(":memory:") if pooled else None
    db = (
        DatabaseService("sqlite:///:memory:", connection_pool=pool)
        if facade
        else SQLiteProvider(":memory:", connection_pool=pool)
    )
    if isinstance(db, DatabaseService):
        await db.boot()
    else:
        await db.connect()
    try:
        assert isinstance(db, CommittedReadGuardProtocol)
        assert db.supports_committed_read_guard_v1 is True
        assert db.committed_read_state() is CommittedReadState.SAFE
        async with db.transaction():
            assert db.committed_read_state() is CommittedReadState.IN_TRANSACTION
        assert db.committed_read_state() is CommittedReadState.SAFE

        async def abort() -> None:
            async with db.transaction():
                assert db.committed_read_state() is CommittedReadState.IN_TRANSACTION
                raise ValueError("abort")

        with pytest.raises(ValueError, match="abort"):
            await abort()
        assert db.committed_read_state() is CommittedReadState.SAFE
    finally:
        if isinstance(db, DatabaseService):
            await db.shutdown()
        else:
            await db.disconnect()


@pytest.mark.parametrize("marker", [False, 1, None, "true"])
@pytest.mark.parametrize(
    "name", ["supports_outbox_committed_reads_v1", "supports_committed_read_guard_v1"]
)
def test_missing_or_truthy_driver_capability_is_refused(
    monkeypatch: pytest.MonkeyPatch, marker: object, name: str
) -> None:
    db = SQLiteProvider(":memory:")
    monkeypatch.setattr(db, name, marker)
    assert db.committed_read_state() is CommittedReadState.UNSUPPORTED_PROVIDER


@pytest.mark.parametrize("active", [None, 0, "false", object()])
def test_unobservable_transaction_is_not_safe(
    monkeypatch: pytest.MonkeyPatch, active: object
) -> None:
    db = SQLiteProvider(":memory:")
    monkeypatch.setattr(
        db, "transaction_manager", SimpleNamespace(in_transaction=active)
    )
    assert db.committed_read_state() is CommittedReadState.UNOBSERVABLE_TRANSACTION


def test_inherited_capabilities_do_not_certify_subclasses() -> None:
    class Driver(SQLiteProvider):
        pass

    class Pool(SQLiteConnectionPool):
        pass

    class Facade(DatabaseService):
        pass

    assert (
        Driver(":memory:").committed_read_state()
        is CommittedReadState.UNSUPPORTED_PROVIDER
    )
    assert (
        SQLiteProvider(
            ":memory:", connection_pool=Pool(":memory:")
        ).committed_read_state()
        is CommittedReadState.UNSUPPORTED_POOL
    )
    assert (
        Facade("sqlite:///:memory:").committed_read_state()
        is CommittedReadState.UNSUPPORTED_PROVIDER
    )
    assert (
        DatabaseService("sqlite:///:memory:").committed_read_state()
        is CommittedReadState.UNSUPPORTED_PROVIDER
    )


@pytest.mark.parametrize("marker", [False, 1, None, "true"])
def test_pool_capability_must_be_literal_true(
    monkeypatch: pytest.MonkeyPatch, marker: object
) -> None:
    pool = SQLiteConnectionPool(":memory:")
    monkeypatch.setattr(pool, "supports_outbox_committed_reads_v1", marker)
    assert (
        SQLiteProvider(":memory:", connection_pool=pool).committed_read_state()
        is CommittedReadState.UNSUPPORTED_POOL
    )
