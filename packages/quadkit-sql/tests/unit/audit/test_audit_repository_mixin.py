"""Tests for the audit repository mixin (AuditRepositoryMixin)."""

from __future__ import annotations

from types import SimpleNamespace

from quadkit.sql.audit.mixin import AuditRepositoryMixin


class _RecorderLogger:
    def __init__(self, fail: bool = False) -> None:
        self.entries: list = []
        self.fail = fail

    async def log(self, entry) -> None:
        if self.fail:
            msg = "audit sink down"
            raise RuntimeError(msg)
        self.entries.append(entry)


class _Entity:
    def __init__(self, id: int = 1, name: str = "a", **extra) -> None:
        self.id = id
        self.name = name
        for k, v in extra.items():
            setattr(self, k, v)


class _Base:
    """Stand-in for the repository base the mixin augments."""

    def __init__(self, *, store: dict | None = None) -> None:
        self.key_field = "id"
        self.table_name = "things"
        self.store = store if store is not None else {}
        self.created: list = []
        self.deleted: list = []

    def _entity_to_dict(self, entity) -> dict:
        return {k: v for k, v in vars(entity).items() if not k.startswith("_")}

    async def create(self, entity) -> _Entity:
        self.store[entity.id] = entity
        self.created.append(entity)
        return entity

    async def update(self, entity) -> _Entity:
        self.store[entity.id] = entity
        return entity

    async def find_by_id(self, key):
        return self.store.get(key)

    async def delete(self, key) -> bool:
        if key in self.store:
            del self.store[key]
            self.deleted.append(key)
            return True
        return False


class _Repo(AuditRepositoryMixin, _Base):
    pass


def _repo(logger=None, store=None, user_id: str | None = None) -> _Repo:
    ctx = SimpleNamespace(user_id=user_id)
    return _Repo(audit_logger=logger, db_ctx=ctx, store=store)


class TestInitAndUser:
    def test_no_logger_noop(self) -> None:
        repo = _repo()
        assert repo.audit_logger is None

    def test_get_current_user_from_ctx(self) -> None:
        assert _repo(user_id="u-9")._get_current_user() == "u-9"
        assert _repo(user_id=None)._get_current_user() is None

    def test_get_current_user_without_ctx(self) -> None:
        repo = _Repo(audit_logger=None, db_ctx=None)
        assert repo._get_current_user() is None


class TestCreate:
    async def test_logs_insert(self) -> None:
        logger = _RecorderLogger()
        repo = _repo(logger, user_id="u-1")
        entity = _Entity(id=7, name="z")
        result = await repo.create(entity)
        assert result is entity
        assert len(logger.entries) == 1
        entry = logger.entries[0]
        assert entry.action == "INSERT"
        assert entry.actor_id == "u-1"
        assert entry.resource_type == "things"
        assert entry.resource_id == "7"
        assert entry.old_values == {}
        assert entry.new_values == {"id": 7, "name": "z"}
        assert entry.source == "sql"

    async def test_no_logger_skips(self) -> None:
        repo = _repo()
        assert await repo.create(_Entity()) is not None


class TestUpdate:
    async def test_logs_old_and_new(self) -> None:
        logger = _RecorderLogger()
        store = {5: _Entity(id=5, name="before")}
        repo = _repo(logger, store=store, user_id="u-2")
        entity = _Entity(id=5, name="after")
        await repo.update(entity)
        assert len(logger.entries) == 1
        entry = logger.entries[0]
        assert entry.action == "UPDATE"
        assert entry.old_values == {"id": 5, "name": "before"}
        assert entry.new_values == {"id": 5, "name": "after"}

    async def test_update_missing_entity_empty_old(self) -> None:
        logger = _RecorderLogger()
        repo = _repo(logger, store={})
        await repo.update(_Entity(id=42, name="x"))
        assert logger.entries[0].old_values == {}


class TestDelete:
    async def test_logs_delete(self) -> None:
        logger = _RecorderLogger()
        store = {9: _Entity(id=9, name="gone")}
        repo = _repo(logger, store=store, user_id="u-3")
        result = await repo.delete(9)
        assert result is True
        entry = logger.entries[0]
        assert entry.action == "DELETE"
        assert entry.resource_id == "9"
        assert entry.old_values == {"id": 9, "name": "gone"}
        assert entry.new_values == {}

    async def test_delete_missing_no_entry(self) -> None:
        logger = _RecorderLogger()
        repo = _repo(logger, store={})
        assert await repo.delete(123) is False
        assert logger.entries == []


class TestFailureIsolation:
    async def test_audit_failure_does_not_break_operation(self) -> None:
        logger = _RecorderLogger(fail=True)
        repo = _repo(logger)
        entity = _Entity(id=1, name="a")
        result = await repo.create(entity)  # must not raise
        assert result is entity

    async def test_audit_failure_on_delete(self) -> None:
        logger = _RecorderLogger(fail=True)
        store = {1: _Entity(id=1)}
        repo = _repo(logger, store=store)
        assert await repo.delete(1) is True  # must not raise

    async def test_entity_without_id_skips_logging(self) -> None:
        logger = _RecorderLogger()
        repo = _repo(logger)

        class _NoId:
            name = "no id here"

        await repo._log_change(_NoId(), "INSERT", {}, {"name": "x"})
        assert logger.entries == []
