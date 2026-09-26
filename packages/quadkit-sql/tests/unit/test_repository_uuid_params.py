from types import SimpleNamespace
import uuid

import pytest

from quadkit.sql.repositories.base import SQLRepository


class FakeProvider:
    async def execute_query(self, query, params=None, **kwargs):
        # params should be a list with a single stringified UUID
        assert params is not None
        assert isinstance(
            params[0], str,
        ), f"Param was not coerced to str: {type(params[0])}"
        return SimpleNamespace(success=True, rows=[{"id": params[0], "username": "u"}])


class DummyRepo(SQLRepository):
    def __init__(self, provider):
        super().__init__(provider, "admin_users")

    async def find_by_id(self, key, columns=None, include_deleted=False):
        return await super().find_by_id(key, columns, include_deleted)

    async def find_many(self, **kwargs): return []
    async def find_one(self, **kwargs): return None
    async def count(self, **kwargs): return 0
    async def exists(self, **kwargs): return False
    async def create(self, entity): return entity
    async def update(self, entity): return entity
    async def delete_by_id(self, key): return True

    def _entity_to_dict(self, entity):
        return {}

    def _row_to_entity(self, row):
        return row


@pytest.mark.asyncio
async def test_find_by_id_coerces_uuid_to_str():
    prov = FakeProvider()
    repo = DummyRepo(prov)
    test_uuid = uuid.UUID(int=1)

    res = await repo.find_by_id(test_uuid)
    assert res["id"] == str(test_uuid)
