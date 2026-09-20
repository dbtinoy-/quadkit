"""Factories, async helpers, smoke checks and snapshot assertions."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from _pytest.outcomes import Skipped
from quadkit.testing.lib.async_helper import AsyncTestHelper
from quadkit.testing.lib.factory import TestDataFactory
from quadkit.testing.lib.smoke import assert_contracts_resolve
from quadkit.testing.lib.snapshots import SnapshotAsserter, SnapshotMismatchError

# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------


def test_test_data_factory_creators() -> None:
    f = TestDataFactory()
    user = f.create_user("u1", email="x@y.z")
    assert user["id"] == "u1"
    assert user["email"] == "x@y.z"
    assert user["roles"] == ["user"]

    user2 = f.create_user()
    assert user2["id"] != "u1"
    assert user2["username"].startswith("user_")

    task = f.create_task("t1", status="done")
    assert task["id"] == "t1"
    assert task["status"] == "done"
    assert f.create_task()["priority"] == "normal"

    msg = f.create_message("topic-a", payload={"k": 1})
    assert msg["topic"] == "topic-a"
    assert msg["payload"] == {"k": 1}

    req = f.create_request("POST", "/x", headers={"a": "b"}, body={"c": 1})
    assert req["method"] == "POST"
    assert req["path"] == "/x"
    assert req["headers"] == {"a": "b"}
    assert req["body"] == {"c": 1}
    assert f.create_request()["body"] is None


# ---------------------------------------------------------------------------
# async_helper
# ---------------------------------------------------------------------------


async def test_wait_for_condition_immediate_and_delayed() -> None:
    assert await AsyncTestHelper.wait_for_condition(lambda: True, timeout=0.2)
    state = {"n": 0}

    def flaky() -> bool:
        state["n"] += 1
        return state["n"] >= 3

    assert await AsyncTestHelper.wait_for_condition(flaky, timeout=2.0, interval=0.01)
    assert state["n"] >= 3


async def test_wait_for_condition_timeout() -> None:
    assert (
        await AsyncTestHelper.wait_for_condition(lambda: False, timeout=0.05) is False
    )


async def test_collect_async_results_returns_exceptions() -> None:
    async def good(v: int) -> int:
        return v

    async def bad() -> None:
        msg = "boom"
        raise ValueError(msg)

    results = await AsyncTestHelper.collect_async_results([good(1), bad(), good(3)])
    assert results[0] == 1
    assert results[2] == 3
    assert isinstance(results[1], ValueError)


async def test_run_with_timeout_success_and_failure() -> None:
    async def quick() -> str:
        return "done"

    assert await AsyncTestHelper.run_with_timeout(quick(), timeout=1.0) == "done"

    async def slow() -> None:
        import asyncio

        await asyncio.sleep(0.5)

    with pytest.raises(TimeoutError, match=r"Operation timed out after 0\.05 seconds"):
        await AsyncTestHelper.run_with_timeout(slow(), timeout=0.05)


# ---------------------------------------------------------------------------
# smoke
# ---------------------------------------------------------------------------


class _BadContract:
    pass


async def test_assert_contracts_resolve() -> None:
    container = MagicMock()

    async def resolve(contract: type, bypass_visibility: bool = False) -> object:
        assert bypass_visibility is True
        if contract is _BadContract:
            msg = "no provider"
            raise RuntimeError(msg)
        return object()

    container.resolve = resolve
    await assert_contracts_resolve(container, [dict, list])

    with pytest.raises(
        AssertionError, match="contract failed to resolve: _BadContract: no provider"
    ):
        await assert_contracts_resolve(container, [_BadContract])


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------


def test_snapshot_update_exists_delete(tmp_path: Any) -> None:
    a = SnapshotAsserter(tmp_path)
    assert a.exists("s1") is False
    p = a.update("s1", {"a": 1})
    assert p == tmp_path / "s1.json"
    # quadkit.serialization dumps compactly (indent is ignored by the framework serializer).
    assert p.read_text() == '{"a":1}\n'
    assert a.exists("s1") is True
    assert a.delete("s1") is True
    assert a.delete("s1") is False
    assert a.exists("s1") is False


def test_snapshot_match_first_run_skips_then_matches(tmp_path: Any) -> None:
    a = SnapshotAsserter(tmp_path)
    with pytest.raises(Skipped):
        a.assert_match("s2", {"v": 2})
    assert a.exists("s2") is True
    # Identical value (JSON-normalised) passes.
    a.assert_match("s2", {"v": 2})
    with pytest.raises(SnapshotMismatchError) as exc:
        a.assert_match("s2", {"v": 3})
    assert "s2" in str(exc.value)
    assert exc.value.expected == {"v": 2}
    assert exc.value.actual == {"v": 3}
    assert SnapshotMismatchError._code == "QK_ERR_TEST_012"


def test_snapshot_numeric_normalisation(tmp_path: Any) -> None:
    a = SnapshotAsserter(tmp_path)
    a.update("s3", {"n": 1})
    # int vs float compare equal after JSON round-trip.
    a.assert_match("s3", {"n": 1.0})


# ---------------------------------------------------------------------------
