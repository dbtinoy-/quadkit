"""Tests for quadkit.testing.lib helpers (assertions, factory, async, smoke, snapshots, stubs, admin)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.module.base import Module
from quadkit.di.module.constants import MODULE_METADATA_ATTR
from quadkit.result import Err, Ok
from quadkit.testing import lib
from quadkit.testing.generators_contract import assert_contributor_generators_render
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
from quadkit.testing.lib.factory import TestDataFactory
from quadkit.testing.lib.smoke import assert_contracts_resolve
from quadkit.testing.lib.stubs import ConfigurationError, assert_stub_modules

ValidationError = type("ValidationError", (Exception,), {})


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
    # plans/09182026 S-03: the helpers are classes; no shared instances exist.
    assert not hasattr(lib, "test_assertions")
    assert not hasattr(lib, "test_data_factory")
    assert lib.TestAssertions is TestAssertions
    assert lib.TestDataFactory is TestDataFactory
    assert isinstance(TestAssertions(), TestAssertions)
    assert lib.AsyncTestHelper is AsyncTestHelper
    assert lib.assert_contracts_resolve is assert_contracts_resolve
    assert lib.assert_ok(Ok(3)) == 3
    assert isinstance(TestDataFactory(), TestDataFactory)
