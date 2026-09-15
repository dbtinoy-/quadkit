"""Tests for the pytest fixture modules (fixtures/*).

Fixtures are exercised by invoking the wrapped fixture functions directly
(sync fixtures by call, async-generator fixtures by driving the generator
protocol), which tests both the fixture bodies and their teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace
from typing import Any

import pytest

from quadkit.testing import fakes
from quadkit.testing.clients.ai import AITestBed, AITestClient, AITestData
from quadkit.testing.clients.db import DatabaseTestBed, DatabaseTestClient
from quadkit.testing.clients.tasks import TaskTestBed, TaskTestClient
from quadkit.testing.clients.web import WebTestBed, WebTestClient
from quadkit.testing.fixtures import _lazy, ai, core, db, tasks, web
from quadkit.testing.fixtures.bed import TestEnvironment
from quadkit.testing.fixtures.container import ContainerTestFixture
from quadkit.testing.plugins import pytest as plugin


def _wrapped(fixture: Any) -> Any:
    """Return the original function behind a @pytest.fixture decorator."""
    return fixture.__wrapped__


def _drive(gen: Any) -> Any:
    """Run an async fixture result: drive generators (with teardown) or await coroutines."""

    async def _run() -> Any:
        if asyncio.iscoroutine(gen):
            return await gen
        value = await gen.__anext__()
        with contextlib.suppress(StopAsyncIteration):
            await gen.__anext__()
        return value

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# core fixtures
# ---------------------------------------------------------------------------


class TestCoreFixtures:
    def test_fake_service_fixtures_return_fresh_instances(self) -> None:
        pairs = [
            (core.fake_event_bus, fakes.FakeEventBus),
            (core.fake_logger, fakes.FakeLogger),
            (core.fake_cache, fakes.FakeCache),
            (core.fake_command_bus, fakes.FakeCommandBus),
            (core.fake_query_bus, fakes.FakeQueryBus),
            (core.fake_state_store, fakes.FakeStateStore),
            (core.fake_metrics, fakes.FakeMetricsCollector),
            (core.fake_clock, fakes.FakeClock),
            (core.fake_unit_of_work, fakes.FakeUnitOfWork),
        ]
        for fixture, expected_type in pairs:
            first = _wrapped(fixture)()
            second = _wrapped(fixture)()
            assert isinstance(first, expected_type)
            assert first is not second

    def test_fake_config_uses_param(self) -> None:
        cfg = _wrapped(core.fake_config)(SimpleNamespace(param={"a.b": 7}))
        assert isinstance(cfg, fakes.FakeConfig)
        assert cfg.get("a.b") == 7

    def test_fake_config_defaults_empty(self) -> None:
        cfg = _wrapped(core.fake_config)(SimpleNamespace(param=None))
        assert isinstance(cfg, fakes.FakeConfig)

    def test_test_data_and_assertions_expose_lib(self) -> None:
        from quadkit.testing.lib import test_assertions, test_data_factory

        assert _wrapped(core.test_data)() is test_data_factory
        assert _wrapped(core.assertions)() is test_assertions

    def test_test_bed_yields_and_tears_down(self) -> None:
        bed = _drive(_wrapped(core.test_bed)())
        assert isinstance(bed, TestEnvironment)

    def test_test_container_yields_and_disposes(self) -> None:
        container = _drive(_wrapped(core.test_container)())
        assert isinstance(container, ContainerTestFixture)


# ---------------------------------------------------------------------------
# db fixtures
# ---------------------------------------------------------------------------


class TestDbFixtures:
    def test_mock_connection_shape(self) -> None:
        from unittest.mock import AsyncMock

        conn = _wrapped(db.mock_connection)()
        assert isinstance(conn.execute, AsyncMock)
        assert isinstance(conn.close, AsyncMock)

        async def _run() -> None:
            async with conn.transaction():
                pass

        asyncio.run(_run())

    def test_mock_connection_pool_shape(self) -> None:
        pool = _wrapped(db.mock_connection_pool)()
        assert pool.health_check() == {"status": "healthy"}
        assert pool.get_stats() == {"connections": 5}

    def test_sample_data_shapes(self) -> None:
        users = _wrapped(db.sample_user_data)()
        orders = _wrapped(db.sample_order_data)()
        products = _wrapped(db.sample_product_data)()
        assert [u["id"] for u in users] == [1, 2, 3]
        assert users[0]["email"] == "alice@example.com"
        assert [o["status"] for o in orders] == ["completed", "pending", "shipped"]
        assert [p["category"] for p in products] == [
            "electronics",
            "tools",
            "accessories",
        ]

    def test_database_provider_defaults_none(self) -> None:
        assert _wrapped(db.database_provider)() is None

    def test_db_test_bed_yields_started_bed(self) -> None:
        bed = _drive(_wrapped(db.db_test_bed)())
        assert isinstance(bed, DatabaseTestBed)

    def test_test_database_client(self) -> None:
        client = _drive(_wrapped(db.test_database_client)())
        assert isinstance(client, DatabaseTestClient)

    def test_seeded_database_creates_tables_and_seeds(self) -> None:
        # The bed must stay open (connected) while the dependent fixture runs.
        async def _run() -> Any:
            bed_gen = _wrapped(db.db_test_bed)()
            bed = await bed_gen.__anext__()
            try:
                return await _wrapped(db.seeded_database)(
                    bed,
                    _wrapped(db.sample_user_data)(),
                    _wrapped(db.sample_order_data)(),
                    _wrapped(db.sample_product_data)(),
                )
            finally:
                with contextlib.suppress(StopAsyncIteration):
                    await bed_gen.__anext__()

        assert asyncio.run(_run()) is not None

    def test_clean_database(self) -> None:
        async def _run() -> Any:
            bed_gen = _wrapped(db.db_test_bed)()
            bed = await bed_gen.__anext__()
            try:
                return await _wrapped(db.clean_database)(bed), bed
            finally:
                with contextlib.suppress(StopAsyncIteration):
                    await bed_gen.__anext__()

        cleaned, bed = asyncio.run(_run())
        assert cleaned is bed

    def test_db_transaction_skips_without_provider(self) -> None:
        gen = _wrapped(db.db_transaction)(None)
        with pytest.raises(pytest.skip.Exception, match="database_provider"):
            asyncio.run(gen.__anext__())

    def test_db_transaction_begins_and_rolls_back(self) -> None:
        class _FakeScoped:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *exc: object) -> bool:
                return False

        class _FakeConn:
            def __init__(self) -> None:
                self.statements: list[str] = []

            async def execute(self, sql: str, *args: Any) -> None:
                self.statements.append(sql)

        class _FakeProvider:
            def __init__(self) -> None:
                self.conn = _FakeConn()

            def scoped_context(self) -> _FakeScoped:
                return _FakeScoped()

            async def get_scoped_connection(self) -> _FakeConn:
                return self.conn

        provider = _FakeProvider()
        conn = _drive(_wrapped(db.db_transaction)(provider))
        assert conn is provider.conn
        assert conn.statements == ["BEGIN", "ROLLBACK"]


# ---------------------------------------------------------------------------
# web fixtures
# ---------------------------------------------------------------------------


class TestWebFixtures:
    def test_mock_web_request_shape(self) -> None:
        request = _wrapped(web.mock_web_request)()
        assert request.method == "GET"
        assert request.url == "http://testserver/test"
        assert request.headers == {"Content-Type": "application/json"}

    def test_mock_web_response(self) -> None:
        response = _wrapped(web.mock_web_response)()
        assert response is not None

    def test_sample_web_data(self) -> None:
        user = _wrapped(web.sample_web_user_data)()
        post = _wrapped(web.sample_web_post_data)()
        assert user["username"] == "testuser"
        assert post["author_id"] == 1

    def test_web_test_client(self) -> None:
        client = _wrapped(web.web_test_client)()
        assert isinstance(client, WebTestClient)

    def test_web_test_bed(self) -> None:
        bed = _drive(_wrapped(web.web_test_bed)())
        assert isinstance(bed, WebTestBed)

    def test_authenticated_web_client(self) -> None:
        client = _wrapped(web.web_test_client)()
        authed = _drive(_wrapped(web.authenticated_web_client)(client))
        assert authed is client

    def test_app_bed_yields_none_without_entry_point(self) -> None:
        bed = _drive(_wrapped(web.app_bed)())
        assert bed is None


# ---------------------------------------------------------------------------
# ai fixtures
# ---------------------------------------------------------------------------


class TestAiFixtures:
    def test_bed_client_data(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        assert isinstance(bed, AITestBed)
        client = _wrapped(ai.intelligence_test_client)(bed)
        assert isinstance(client, AITestClient)
        data = _wrapped(ai.intelligence_test_data)()
        assert isinstance(data, AITestData)

    def test_sample_data(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        messages = _wrapped(ai.sample_chat_messages)(bed)
        assert len(messages) == 2
        assert messages[1].content == "What is the capital of France?"
        documents = _wrapped(ai.sample_documents)(bed)
        assert [d.id for d in documents] == ["doc1", "doc2", "doc3"]
        features = _wrapped(ai.sample_features)(bed)
        assert features["category"] == "positive"
        responses = _wrapped(ai.sample_llm_responses)()
        assert len(responses) == 4
        predictions = _wrapped(ai.sample_predictions)()
        assert [p["prediction"] for p in predictions] == [
            "positive",
            "negative",
            "neutral",
        ]

    def test_bed_backed_async_clients(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        llm = _drive(_wrapped(ai.llm_client)(bed))
        assert llm is bed.mock_llm
        store = _drive(_wrapped(ai.vector_store)(bed))
        assert store is bed.mock_vector_store
        predictor = _drive(_wrapped(ai.ml_predictor)(bed))
        assert predictor is bed.mock_ml_predictor

    def test_mock_fixtures_delegate_to_bed(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        assert _wrapped(ai.mock_llm_client)(bed) is bed.mock_llm
        assert _wrapped(ai.mock_vector_store)(bed) is bed.mock_vector_store
        assert _wrapped(ai.mock_ml_predictor)(bed) is bed.mock_ml_predictor

    def test_mock_clients_are_awaitable(self) -> None:
        bed = AITestBed()

        async def _run() -> None:
            result = await bed.mock_llm.complete("hello")
            assert result.content == "Mock response"
            ids = await bed.mock_vector_store.add(["d"])
            assert ids == ["doc1", "doc2", "doc3"]
            hits = await bed.mock_vector_store.search("q")
            assert len(hits) == 2
            prediction = await bed.mock_ml_predictor.predict({"x": 1})
            assert prediction.result == "positive"

        asyncio.run(_run())

    def test_populated_vector_store(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        store = bed.mock_vector_store
        documents = _wrapped(ai.sample_documents)(bed)
        populated = _drive(_wrapped(ai.populated_vector_store)(store, documents))
        assert populated is store
        store.add.assert_awaited_once_with(documents)

    def test_intelligence_assertions(self) -> None:
        bed = _wrapped(ai.intelligence_test_bed)()
        helpers = _wrapped(ai.intelligence_assertions)(bed.create_test_client())
        assert set(helpers) == {
            "assert_llm_completions_count",
            "assert_vector_searches_count",
            "assert_ml_predictions_count",
        }
        for helper in helpers.values():
            assert callable(helper)


# ---------------------------------------------------------------------------
# tasks fixtures
# ---------------------------------------------------------------------------


class TestTasksFixtures:
    def test_task_test_bed_is_set_up(self) -> None:
        # The bed fixture is an async generator: setup() on first anext,
        # teardown() on close. Consumers must receive a fully set-up bed
        # (mock_queue/mock_executor present) while the context is live.
        gen = _wrapped(tasks.task_test_bed)()

        async def _run() -> None:
            bed = await gen.__anext__()
            try:
                assert isinstance(bed, TaskTestBed)
                assert bed.mock_queue is not None
                assert bed.mock_executor is not None
            finally:
                await gen.aclose()

        asyncio.run(_run())

    def test_task_test_client(self) -> None:
        bed_gen = _wrapped(tasks.task_test_bed)()

        async def _run() -> TaskTestClient:
            bed = await bed_gen.__anext__()
            try:
                client_gen = _wrapped(tasks.task_test_client)(bed)
                client = await client_gen.__anext__()
                try:
                    assert isinstance(client, TaskTestClient)
                    assert client.test_bed is bed
                    return client
                finally:
                    await client_gen.aclose()
            finally:
                await bed_gen.aclose()

        asyncio.run(_run())

    def test_sample_task_data(self) -> None:
        data = _wrapped(tasks.sample_task_data)()
        assert isinstance(data, list)
        assert all(isinstance(row, dict) for row in data)


# ---------------------------------------------------------------------------
# lazy loader + plugin wiring
# ---------------------------------------------------------------------------


class TestFixtureWiring:
    def test_lazy_ai_fixture_loader(self) -> None:
        assert _lazy.is_ai_fixture("llm_client") is True
        assert _lazy.is_ai_fixture("fake_cache") is False
        assert _lazy.get_ai_fixture("llm_client") is ai.llm_client
        with pytest.raises(AttributeError):
            _lazy.get_ai_fixture("no_such_fixture")

    def test_ai_fixtures_are_lazily_exposed_by_package(self) -> None:
        from quadkit.testing import fixtures

        assert fixtures.llm_client is ai.llm_client
        with pytest.raises(AttributeError, match="not_a_fixture"):
            fixtures.__getattr__("not_a_fixture")

    def test_plugin_pytest_plugins_are_importable(self) -> None:
        import importlib

        for module_name in plugin.pytest_plugins:
            assert "messaging" not in module_name  # removed self-import shim
            module = importlib.import_module(module_name)
            assert module is not None

    def test_fixtures_all_matches_module_functions(self) -> None:
        for module in (core, db, web, tasks):
            for name in module.__all__:
                assert hasattr(module, name), f"{module.__name__}.{name} missing"
