"""Tests for the consumer-facing workflow/saga-step decorators."""

from __future__ import annotations

from quadkit.workflow.decorators import saga_step, workflow


class TestWorkflowDecorator:
    async def test_defaults(self) -> None:
        @workflow()
        async def onboarding() -> str:
            return "ok"

        assert onboarding.__workflow__ is True
        assert onboarding.__workflow_name__ == "onboarding"
        assert onboarding.__workflow_timeout__ is None
        assert onboarding.__workflow_retries__ == 0
        assert await onboarding() == "ok"

    async def test_explicit_metadata(self) -> None:
        @workflow(name="wf-1", timeout=300.0, retries=3)
        async def f() -> None:
            return None

        assert f.__workflow_name__ == "wf-1"
        assert f.__workflow_timeout__ == 300.0
        assert f.__workflow_retries__ == 3

    def test_name_defaults_to_function_name(self) -> None:
        @workflow()
        async def my_flow() -> None:
            return None

        assert my_flow.__workflow_name__ == "my_flow"

    def test_metadata_survives_wrapper(self) -> None:
        @workflow(name="w", timeout=1.0, retries=1)
        async def f() -> None:
            return None

        # the returned callable is the wrapper; metadata must be on it
        assert callable(f)
        assert f.__name__ == "f"  # functools.wraps preserved
        assert f.__workflow__ is True
        assert f.__workflow_name__ == "w"

    async def test_passes_args_and_kwargs(self) -> None:
        @workflow()
        async def add(a: int, b: int, extra: int = 0) -> int:
            return a + b + extra

        assert await add(1, 2) == 3
        assert await add(1, 2, extra=10) == 13

    async def test_propagates_exceptions(self) -> None:
        @workflow()
        async def boom() -> None:
            raise ValueError("nope")

        try:
            await boom()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")

    def test_wrapped_pointer(self) -> None:
        @workflow()
        async def f() -> None:
            return None

        assert f.__wrapped__.__name__ == "f"


class TestSagaStepDecorator:
    async def test_defaults(self) -> None:
        @saga_step()
        async def pay() -> str:
            return "paid"

        assert pay.__saga_step__ is True
        assert pay.__saga_step_name__ == "pay"
        assert pay.__saga_compensation__ is None
        assert await pay() == "paid"

    async def test_with_compensation(self) -> None:
        async def release() -> None:
            return None

        @saga_step(name="charge", compensation=release)
        async def charge() -> None:
            return None

        assert charge.__saga_step_name__ == "charge"
        assert charge.__saga_compensation__ is release

    def test_metadata_survives_wrapper(self) -> None:
        @saga_step(name="s1")
        async def step() -> None:
            return None

        assert step.__saga_step__ is True
        assert step.__saga_step_name__ == "s1"
        assert step.__name__ == "step"

    async def test_passes_args(self) -> None:
        @saga_step()
        async def move(amount: int, to: str) -> str:
            return f"{to}:{amount}"

        assert await move(5, "acct") == "acct:5"

    async def test_propagates_exceptions(self) -> None:
        @saga_step()
        async def fail() -> None:
            raise RuntimeError("step failed")

        try:
            await fail()
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected RuntimeError")

    def test_wrapped_pointer(self) -> None:
        @saga_step()
        async def step() -> None:
            return None

        assert step.__wrapped__.__name__ == "step"


class TestDecoratorComposition:
    async def test_workflow_and_saga_step_stack(self) -> None:
        async def comp() -> None:
            return None

        def step(name: str):
            return saga_step(name=name)

        def wf(name: str):
            return workflow(name=name)

        decorated = step("s")(wf("w")(lambda: comp))
        assert decorated.__workflow_name__ == "w"
        assert decorated.__saga_step_name__ == "s"
