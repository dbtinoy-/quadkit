"""Tests for quadkit.testing.harness (testbed, decorators, container, environment) and testkit."""

from __future__ import annotations

import sys
from typing import Any

import pytest
from quadkit.app.base import Application
from quadkit.testing.harness.decorators import override
from quadkit.testing.harness.decorators import testbed as tb_decorator
from quadkit.testing.harness.testbed import AppTestBed, _build_test_client

# ---------------------------------------------------------------------------
# AppTestBed
# ---------------------------------------------------------------------------


class _Service:
    pass


async def test_app_test_bed_from_factory_callable() -> None:
    captured: dict[str, Any] = {}

    def factory() -> Application:
        app = Application(name="harness-test")
        captured["app"] = app
        return app

    async with AppTestBed.from_factory(factory) as bed:
        assert bed.app is captured["app"]
        assert bed.container is bed.app.container
        assert bed.client is None  # no WebProvider → no HTTP client
        assert bed.app.is_running

    assert not captured["app"].is_running


async def test_app_test_bed_from_factory_string(tmp_path: Any) -> None:
    module_path = tmp_path / "harness_app_mod.py"
    module_path.write_text(
        "from quadkit.app.base import Application\n\n"
        "def create_app() -> Application:\n"
        "    return Application(name='string-factory')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        async with AppTestBed.from_factory("harness_app_mod:create_app") as bed:
            assert bed.app.name == "string-factory"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("harness_app_mod", None)


async def test_app_test_bed_from_app_and_overrides() -> None:
    app = Application(name="from-app-test")
    impl = _Service()
    async with AppTestBed.from_app(app, overrides={_Service: impl}) as bed:
        resolved = await bed.container.resolve(_Service)
        assert resolved is impl
    assert not app.is_running


async def test_app_test_bed_overrides_take_effect() -> None:
    class Marker:
        pass

    class_impl = Marker()
    async with AppTestBed.from_factory(
        lambda: Application(name="override-test"), overrides={Marker: class_impl}
    ) as bed:
        assert await bed.container.resolve(Marker) is class_impl


def test_app_test_bed_resolve_factory() -> None:
    def _fn() -> None:
        return None

    assert AppTestBed._resolve_factory(_fn) is _fn

    with pytest.raises(TypeError, match="factory must be a callable"):
        AppTestBed._resolve_factory(123)


async def test_app_test_bed_with_web_provider_has_client() -> None:
    from quadkit.web.di.provider import WebProvider

    def factory() -> Application:
        app = Application(name="web-bed-test")
        app.add_provider(WebProvider())
        return app

    async with AppTestBed.from_factory(factory) as bed:
        assert bed.client is not None
        assert bed.app.is_running


def test_build_test_client() -> None:
    import httpx

    async def _asgi(scope: dict, receive: Any, send: Any) -> None:
        return None

    client = _build_test_client(_asgi)
    assert isinstance(client, httpx.AsyncClient)


# ---------------------------------------------------------------------------
# @testbed / @override decorators
# ---------------------------------------------------------------------------


async def test_tb_decorator_boots_and_injects_bed() -> None:
    seen: dict[str, Any] = {}

    @tb_decorator(lambda: Application(name="decorator-test"))
    class TestFlow:
        async def test_boots(self, bed: Any) -> None:
            seen["bed"] = bed
            seen["running"] = bed.app.is_running

        def test_sync_not_wrapped(self) -> None:
            seen["sync"] = True

        async def helper_not_test(self, bed: Any) -> None:  # noqa: ARG002
            seen["helper"] = True

    instance = TestFlow()
    await instance.test_boots()
    instance.test_sync_not_wrapped()
    instance.helper_not_test(None)  # untouched coroutine — call directly

    assert seen["running"] is True
    assert seen["sync"] is True
    assert not seen.get("helper")
    assert TestFlow.__testbed_factory__  # metadata recorded


async def test_tb_decorator_class_and_method_overrides() -> None:
    class PaymentGateway:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    class_impl = PaymentGateway("class")
    method_impl = PaymentGateway("method")

    @tb_decorator(
        lambda: Application(name="override-merge"),
        overrides={PaymentGateway: class_impl},
    )
    class TestOverrides:
        async def test_class_level(self, bed: Any) -> None:
            assert await bed.container.resolve(PaymentGateway) is class_impl

        @override(PaymentGateway, method_impl)
        async def test_method_level(self, bed: Any) -> None:
            assert await bed.container.resolve(PaymentGateway) is method_impl

    instance = TestOverrides()
    await instance.test_class_level()
    await instance.test_method_level()


async def test_tb_decorator_method_without_bed_param() -> None:
    seen: dict[str, Any] = {}

    @tb_decorator(lambda: Application(name="no-bed-param"))
    class TestNoBed:
        async def test_no_bed(self) -> None:
            seen["called"] = True

    await TestNoBed().test_no_bed()
    assert seen["called"] is True


def test_override_decorator_stacks() -> None:
    class A:
        pass

    class B:
        pass

    def _method() -> None:
        return None

    override(A, 1)(override(B, 2)(_method))
    attrs = _method.__dict__["__testbed_method_overrides__"]
    # Outermost decorator (A) is prepended → lowest priority in the merge dict.
    assert attrs == [(A, 1), (B, 2)]
