"""Pin tests for @use_interceptors — the decorator the router reads.

Global coverage of the container-registered pipeline prefix ordering is
exercised end-to-end by docs/guides/examples/features/test_feature_interceptors.py.
"""

from typing import Any

from quadkit.web.interceptors.decorators import use_interceptors
from quadkit.web.protocols import CallHandlerProtocol, ExecutionContextProtocol


class MarkerInterceptor:
    def __init__(self, name: str = "tag") -> None:
        self.name = name

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        return await next_handler.handle()


class TestUseInterceptorsMetadata:
    def test_attaches_instances_in_order(self) -> None:
        first, second = MarkerInterceptor("a"), MarkerInterceptor("b")

        @use_interceptors(first, second)
        async def handler() -> None:
            pass

        assert getattr(handler, "__interceptors__", []) == [first, second]

    def test_appends_to_existing_attachment(self) -> None:
        first, second = MarkerInterceptor("a"), MarkerInterceptor("b")

        @use_interceptors(second)
        @use_interceptors(first)
        async def handler() -> None:
            pass

        # Decorators apply bottom-up, so execution order follows attachment.
        assert getattr(handler, "__interceptors__", []) == [first, second]

    def test_stamps_controller_classes(self) -> None:
        tag = MarkerInterceptor("class-scope")

        @use_interceptors(tag)
        class Handler:
            pass

        assert getattr(Handler, "__interceptors__", []) == [tag]

    def test_accepts_interceptor_classes(self) -> None:
        @use_interceptors(MarkerInterceptor)
        async def handler() -> None:
            pass

        instances = getattr(handler, "__interceptors__", [])
        assert len(instances) == 1
        assert isinstance(instances[0], MarkerInterceptor)
