"""Tests for quadkit.testing.lib helpers (assertions, factory, async, smoke, snapshots, stubs, admin)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from _pytest.outcomes import Skipped
import pytest

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.module.base import Module
from quadkit.di.module.constants import MODULE_METADATA_ATTR
from quadkit.result import Err, Ok
from quadkit.testing import lib
from quadkit.testing.generators_contract import assert_contributor_generators_render
from quadkit.testing.lib.admin_helpers import (
    AdminResponse,
    AdminTestClient,
    make_resource_record,
)
from quadkit.testing.lib.assertions import (
    TestAssertions,
    assert_all_ok,
    assert_healthy,
    assert_result_err,
    assert_result_err_contains,
    assert_result_err_type,
    assert_result_maps_to,
    assert_result_ok,
    assert_result_ok_value,
)
from quadkit.testing.lib.async_helper import AsyncTestHelper
from quadkit.testing.lib.factory import TestDataFactory, test_data_factory
from quadkit.testing.lib.smoke import assert_contracts_resolve
from quadkit.testing.lib.snapshots import SnapshotAsserter, SnapshotMismatchError
from quadkit.testing.lib.stubs import ConfigurationError, assert_stub_modules

ValidationError = type("ValidationError", (Exception,), {})


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "body",
        json_data: Any = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._text = text
        self._json = json_data

    @property
    def text(self) -> str:
        if self._text is None:
            raise RuntimeError("content unavailable")
        return self._text

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("not json")
        return self._json


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.resp = _FakeResp()

    def set(self, **kwargs: Any) -> None:
        self.resp = _FakeResp(**kwargs)

    def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        self.calls.append(("GET", url, params, headers))
        return self.resp

    def post(self, url: str, data: dict | None = None, headers: dict | None = None):
        self.calls.append(("POST", url, data, headers))
        return self.resp

    def delete(self, url: str, headers: dict | None = None):
        self.calls.append(("DELETE", url, None, headers))
        return self.resp


def _admin() -> tuple[AdminTestClient, _FakeClient]:
    client = _FakeClient()
    return AdminTestClient(client, default_headers={"X-Test": "1"}), client


# ---------------------------------------------------------------------------
# admin_helpers
# ---------------------------------------------------------------------------


def test_admin_response_htmx_helpers() -> None:
    resp = AdminResponse(
        status_code=200,
        headers={"HX-Redirect": "/x", "hx-trigger": "saved"},
    )
    assert resp.is_htmx_redirect() is True
    assert resp.htmx_redirect_url() == "/x"
    assert resp.htmx_trigger() == "saved"

    plain = AdminResponse(status_code=200, headers={"Content-Type": "text/html"})
    assert plain.is_htmx_redirect() is False
    assert plain.htmx_redirect_url() is None
    assert plain.htmx_trigger() is None


def test_admin_url_building_and_prefix_strip() -> None:
    admin, _ = _admin()
    assert admin.url("user") == "/admin/user"
    assert admin.url("user", "123", "edit") == "/admin/user/123/edit"
    stripped = AdminTestClient(_FakeClient(), prefix="/admin/")
    assert stripped.url("item") == "/admin/item"


def test_admin_crud_helpers() -> None:
    admin, fake = _admin()

    admin.list("user", params={"page": "2"})
    admin.detail("user", "42")
    admin.create("user", {"name": "a"})
    admin.update("user", "42", {"name": "b"})
    admin.delete("user", "42")
    admin.bulk_action("user", "archive", ["1", "2"])
    admin.search("user", "jo")

    assert [c[0] for c in fake.calls] == [
        "GET",
        "GET",
        "POST",
        "POST",
        "DELETE",
        "POST",
        "GET",
    ]
    assert fake.calls[0][1] == "/admin/user"
    assert fake.calls[0][2] == {"page": "2"}
    assert fake.calls[1][1] == "/admin/user/42"
    assert fake.calls[2][2] == {"name": "a"}
    assert fake.calls[3][1] == "/admin/user/42/edit"
    assert fake.calls[4][1] == "/admin/user/42"
    assert fake.calls[5][2] == {"action": "archive", "ids": "1,2"}
    assert fake.calls[6][2] == {"search": "jo"}
    # Default HX header + custom header on every call.
    for _, _, _, headers in fake.calls:
        assert headers["HX-Request"] == "true"
        assert headers["X-Test"] == "1"


def test_admin_wrap_json_text_and_errors() -> None:
    admin, fake = _admin()
    fake.set(
        status_code=200,
        headers={"content-type": "application/json"},
        json_data={"ok": True},
        text="{}",
    )
    resp = admin.list("user")
    assert resp.json_data == {"ok": True}
    assert resp.text == "{}"

    # Non-JSON content type → json_data stays None even if json() works.
    fake.set(status_code=204, headers={"content-type": "text/html"})
    assert admin.detail("user", "1").json_data is None

    # json() raising → swallowed, text still captured.
    fake.set(status_code=200, headers={"content-type": "application/json"})
    assert admin.detail("user", "1").json_data is None

    # resp.text raising → swallowed.
    fake.set(status_code=200, text=None)
    resp = admin.list("user")
    assert resp.text == ""


def test_admin_assertions() -> None:
    AdminTestClient.assert_ok(AdminResponse(200))
    AdminTestClient.assert_unprocessable(AdminResponse(422))
    AdminTestClient.assert_contains(AdminResponse(200, text="hello world"), "lo wo")
    AdminTestClient.assert_htmx_trigger(
        AdminResponse(200, headers={"HX-Trigger": "saved,flash"}), "saved"
    )
    AdminTestClient.assert_redirect(AdminResponse(302, headers={"location": "/x"}))
    AdminTestClient.assert_redirect(AdminResponse(200, headers={"HX-Redirect": "/x"}))

    with pytest.raises(AssertionError, match="Expected HTTP 200, got 500"):
        AdminTestClient.assert_ok(AdminResponse(500, text="boom"))
    with pytest.raises(AssertionError, match="Expected a redirect"):
        AdminTestClient.assert_redirect(AdminResponse(200))
    with pytest.raises(AssertionError, match="Expected to find"):
        AdminTestClient.assert_contains(AdminResponse(200, text="nope"), "yes")
    with pytest.raises(AssertionError, match="Expected HX-Trigger"):
        AdminTestClient.assert_htmx_trigger(AdminResponse(200), "saved")
    with pytest.raises(AssertionError, match="Expected HTTP 422, got 200"):
        AdminTestClient.assert_unprocessable(AdminResponse(200))


def test_make_resource_record() -> None:
    rec = make_resource_record("user", name="Alice")
    assert rec["_type"] == "user"
    assert rec["name"] == "Alice"
    assert rec["id"]
    assert rec["created_at"] == "2024-01-01T00:00:00Z"
    rec2 = make_resource_record()
    assert rec2["_type"] == "item"
    assert rec2["id"] != rec["id"]


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

    assert isinstance(test_data_factory, TestDataFactory)


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
# assertions: TestAssertions
# ---------------------------------------------------------------------------


def test_assert_eventually_true() -> None:
    TestAssertions.assert_eventually_true(lambda: True, timeout=0.1)
    state = {"n": 0}

    def flaky() -> bool:
        state["n"] += 1
        return state["n"] >= 2

    TestAssertions.assert_eventually_true(flaky, timeout=1.0)

    with pytest.raises(AssertionError, match="Condition never became true"):
        TestAssertions.assert_eventually_true(lambda: False, timeout=0.05)
    with pytest.raises(AssertionError, match="custom msg"):
        TestAssertions.assert_eventually_true(
            lambda: False, timeout=0.05, message="custom msg"
        )


def test_assert_dict_contains_subset() -> None:
    superset = {"a": 1, "b": 2, "c": 3}
    TestAssertions.assert_dict_contains_subset({"a": 1, "c": 3}, superset)
    with pytest.raises(AssertionError, match="Key 'z' not found"):
        TestAssertions.assert_dict_contains_subset({"z": 9}, superset)
    with pytest.raises(AssertionError, match="Value mismatch for key 'a'"):
        TestAssertions.assert_dict_contains_subset({"a": 99}, superset)
    with pytest.raises(AssertionError, match="custom"):
        TestAssertions.assert_dict_contains_subset(
            {"a": 99}, superset, message="custom"
        )


async def test_assert_async_raises() -> None:
    async def raises() -> None:
        msg = "bad"
        raise ValueError(msg)

    await TestAssertions.assert_async_raises(ValueError, raises(), message="bad")

    async def wrong_type() -> None:
        msg = "bad"
        raise KeyError(msg)

    with pytest.raises(AssertionError, match="Expected ValueError but got KeyError"):
        await TestAssertions.assert_async_raises(ValueError, wrong_type())

    async def no_raise() -> None:
        return None

    with pytest.raises(AssertionError, match="no exception was raised"):
        await TestAssertions.assert_async_raises(ValueError, no_raise())

    with pytest.raises(AssertionError, match="Exception message mismatch"):
        await TestAssertions.assert_async_raises(ValueError, raises(), message="other")


def test_assert_metrics_contain() -> None:
    metrics = {"req.count": 5}
    TestAssertions.assert_metrics_contain(metrics, "req.count")
    TestAssertions.assert_metrics_contain(metrics, "req.count", min_value=5)
    with pytest.raises(AssertionError, match="not found"):
        TestAssertions.assert_metrics_contain(metrics, "missing")
    with pytest.raises(AssertionError, match="less than minimum"):
        TestAssertions.assert_metrics_contain(metrics, "req.count", min_value=10)


# ---------------------------------------------------------------------------
# assertions: Result helpers
# ---------------------------------------------------------------------------


def test_result_helpers() -> None:
    assert assert_result_ok(Ok(7)) == 7
    assert lib.assert_ok(Ok("v")) == "v"
    assert assert_result_ok_value(Ok("v"), "v") is None
    with pytest.raises(AssertionError, match="Expected Ok but got Err"):
        assert_result_ok(Err("e1"))
    with pytest.raises(AssertionError, match="Expected Ok\\('x'\\), got Ok\\('y'\\)"):
        assert_result_ok_value(Ok("y"), "x")

    assert assert_result_err(Err("e2")) == "e2"
    assert lib.assert_err(Err("e3")) == "e3"
    with pytest.raises(AssertionError, match="Expected Err but got Ok"):
        assert_result_err(Ok(1))

    class DomainError(Exception):
        pass

    assert_result_err_type(Err(DomainError("d")), DomainError)
    with pytest.raises(AssertionError, match="Expected Err of type DomainError"):
        assert_result_err_type(Err(ValueError("v")), DomainError)
    with pytest.raises(AssertionError, match="Expected Err of type DomainError"):
        lib.assert_err(Err(ValueError("v")), DomainError)

    assert_result_err_contains(Err(ValueError("not found here")), "not found")
    with pytest.raises(AssertionError, match="Expected error to contain"):
        assert_result_err_contains(Err(ValueError("nope")), "missing")

    assert assert_all_ok([Ok(1), Ok(2)]) == [1, 2]
    with pytest.raises(AssertionError, match=r"Result\[1\] is Err"):
        assert_all_ok([Ok(1), Err("bad")])

    assert_result_maps_to(Ok("ab"), lambda s: s.upper(), "AB")
    with pytest.raises(AssertionError, match="Expected mapped value"):
        assert_result_maps_to(Ok("ab"), lambda s: s.upper(), "AC")


def test_assert_healthy() -> None:
    assert_healthy(
        {
            "db": HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
        }
    )
    with pytest.raises(AssertionError, match="degraded"):
        assert_healthy(
            {
                "db": HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
                "mq": HealthCheckResult(component="mq", status=HealthStatus.DEGRADED),
            }
        )


# ---------------------------------------------------------------------------
# stubs
# ---------------------------------------------------------------------------


def _stub_module_graph(*classes: type) -> SimpleNamespace:
    nodes = {cls: SimpleNamespace(name=cls.__name__) for cls in classes}
    return SimpleNamespace(nodes=nodes)


def test_assert_stub_modules_ignores_when_not_testing() -> None:
    class RealStubbed(Module):
        pass

    setattr(
        RealStubbed,
        MODULE_METADATA_ATTR,
        SimpleNamespace(require_stub=True),
    )
    # testing_mode=False → no error even without stub() override.
    assert_stub_modules(_stub_module_graph(RealStubbed), testing_mode=False)


def test_assert_stub_modules_raises_for_missing_stub_override() -> None:
    class NoStub(Module):
        pass

    setattr(NoStub, MODULE_METADATA_ATTR, SimpleNamespace(require_stub=True))
    with pytest.raises(ConfigurationError, match="does not override stub\\(\\)"):
        assert_stub_modules(_stub_module_graph(NoStub), testing_mode=True)
    assert ConfigurationError._code == "QK_ERR_TEST_011"


def test_assert_stub_modules_passes_with_stub_override() -> None:
    class WithStub(Module):
        pass

    setattr(WithStub, MODULE_METADATA_ATTR, SimpleNamespace(require_stub=True))

    @classmethod
    def _stub(cls: type, config: Any = None) -> object:
        return object()

    WithStub.stub = _stub
    assert_stub_modules(_stub_module_graph(WithStub), testing_mode=True)


def test_assert_stub_modules_ignores_non_stub_and_metaless() -> None:
    class OptionalStub(Module):
        pass

    setattr(OptionalStub, MODULE_METADATA_ATTR, SimpleNamespace(require_stub=False))

    class NoMeta(Module):
        pass

    assert_stub_modules(_stub_module_graph(OptionalStub, NoMeta), testing_mode=True)


def test_assert_stub_modules_tolerates_non_callable_stub() -> None:
    class WeirdStub(Module):
        pass

    setattr(WeirdStub, MODULE_METADATA_ATTR, SimpleNamespace(require_stub=True))
    WeirdStub.stub = 42  # type: ignore[assignment]
    # AttributeError inside the check is swallowed → no raise.
    assert_stub_modules(_stub_module_graph(WeirdStub), testing_mode=True)


# ---------------------------------------------------------------------------
# generators_contract
# ---------------------------------------------------------------------------


def _write_generator_module(tmp_path: Any, name: str, body: str) -> str:
    p = tmp_path / f"{name}.py"
    p.write_text(body, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        __import__(name)
    finally:
        sys.path.remove(str(tmp_path))
    return name


def test_generators_contract_renders_and_counts(
    tmp_path: Any, monkeypatch: Any
) -> None:
    mod_name = _write_generator_module(
        tmp_path,
        "gc_gen_a",
        """
from types import SimpleNamespace


class WritesGen:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir

    def generate(self, name, output_dir=None):
        import pathlib
        p = pathlib.Path(output_dir or ".") / f"{name}.txt"
        p.write_text("hello " + name)
        return SimpleNamespace(
            files_created=[str(p)], files_overwritten=[], staged=[]
        )
""",
    )
    contributor = SimpleNamespace(
        get_generators=lambda: [
            SimpleNamespace(
                name="writes",
                generator_path=f"{mod_name}:WritesGen",
                contributor="c1",
            )
        ]
    )
    cwd_before = __import__("pathlib").Path.cwd()
    count = assert_contributor_generators_render(contributor, tmp_path=tmp_path)
    assert count == 1
    assert __import__("pathlib").Path.cwd() == cwd_before
    out = tmp_path / "c1" / "writes"
    assert (out / "demo.txt").read_text() == "hello demo"


def test_generators_contract_skip_and_no_output(
    tmp_path: Any,
) -> None:
    mod_name = _write_generator_module(
        tmp_path,
        "gc_gen_b",
        """
from types import SimpleNamespace


class NoArgGen:
    def generate(self, name, output_dir=None):
        return SimpleNamespace(
            files_created=[], files_overwritten=[], staged=[("src", "dst")]
        )


class EmptyGen:
    def generate(self, name, output_dir=None):
        return SimpleNamespace(files_created=[], files_overwritten=[], staged=[])
""",
    )
    definitions = [
        SimpleNamespace(
            name="noarg", generator_path=f"{mod_name}:NoArgGen", contributor="c2"
        ),
        SimpleNamespace(
            name="empty", generator_path=f"{mod_name}:EmptyGen", contributor="c2"
        ),
    ]
    contributor = SimpleNamespace(get_generators=lambda: list(definitions))

    # Both skipped → 0 exercised, no assertions.
    assert (
        assert_contributor_generators_render(
            contributor, tmp_path=tmp_path, skip=frozenset({"noarg", "empty"})
        )
        == 0
    )
    # staged tuple counts as output; no-arg constructor fallback works.
    assert (
        assert_contributor_generators_render(
            contributor, tmp_path=tmp_path, skip=frozenset({"empty"})
        )
        == 1
    )
    with pytest.raises(AssertionError, match="generator 'empty' produced no output"):
        assert_contributor_generators_render(
            contributor, tmp_path=tmp_path, skip=frozenset({"noarg"})
        )


def test_lib_reexports() -> None:
    assert lib.test_assertions is TestAssertions() or isinstance(
        lib.test_assertions, TestAssertions
    )
    assert isinstance(lib.test_data_factory, TestDataFactory)
    assert lib.AsyncTestHelper is AsyncTestHelper
    assert lib.assert_contracts_resolve is assert_contracts_resolve
    assert lib.assert_ok(Ok(3)) == 3
    # lib/__init__ builds its own convenience instance.
    assert isinstance(lib.test_data_factory, TestDataFactory)
