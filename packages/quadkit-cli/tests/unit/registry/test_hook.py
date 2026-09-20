from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.cli.registry.hook import (
    ErrorHandlingHook,
    Hook,
    HookContext,
    HookExecutor,
    HookPhase,
    HookRegistry,
    HookResult,
    LoggingHook,
    TimingHook,
    ValidationHook,
    create_validation_hook,
)


class TestHookContext:
    def test_defaults(self) -> None:
        ctx = HookContext()
        assert ctx.command == ""
        assert ctx.args == ()
        assert ctx.kwargs == {}
        assert ctx.result is None
        assert ctx.error is None

    def test_custom(self) -> None:
        ctx = HookContext(command="test", args=(1,), kwargs={"a": 1})
        assert ctx.command == "test"
        assert ctx.args == (1,)


class TestHookResult:
    def test_success(self) -> None:
        r = HookResult(success=True)
        assert r.success is True
        assert r.message == ""

    def test_failure(self) -> None:
        r = HookResult(success=False, message="failed")
        assert r.success is False
        assert r.message == "failed"


class TestHook:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Hook()

    def test_should_run_default(self) -> None:
        class ConcreteHook(Hook):
            name = "test"
            phase = HookPhase.PRE_COMMAND
            async def execute(self, context):
                return HookResult(success=True)

        h = ConcreteHook()
        assert h.should_run(HookContext()) is True


class TestLoggingHook:
    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        h = LoggingHook()
        result = await h.execute(HookContext())
        assert result.success is True
    def test_phase(self) -> None:
        assert LoggingHook().phase == HookPhase.PRE_COMMAND
    def test_priority(self) -> None:
        assert LoggingHook().priority == 50


class TestTimingHook:
    @pytest.mark.asyncio
    async def test_execute_adds_timestamp(self) -> None:
        h = TimingHook()
        ctx = HookContext()
        result = await h.execute(ctx)
        assert result.success is True
        assert "start_time" in ctx.metadata
    def test_priority(self) -> None:
        assert TimingHook().priority == 10


class TestErrorHandlingHook:
    @pytest.mark.asyncio
    async def test_no_error(self) -> None:
        h = ErrorHandlingHook()
        result = await h.execute(HookContext())
        assert result.success is True

    @pytest.mark.asyncio
    async def test_with_error(self) -> None:
        h = ErrorHandlingHook()
        ctx = HookContext(error=ValueError("test error"))
        result = await h.execute(ctx)
        assert result.success is False
        assert "test error" in result.message


class TestValidationHook:
    @pytest.mark.asyncio
    async def test_validator_passes(self) -> None:
        validator = lambda ctx: True
        h = ValidationHook(validator)
        result = await h.execute(HookContext())
        assert result.success is True

    @pytest.mark.asyncio
    async def test_validator_fails(self) -> None:
        validator = lambda ctx: False
        h = ValidationHook(validator)
        result = await h.execute(HookContext())
        assert result.success is False


class TestHookRegistry:
    def test_register_and_get(self) -> None:
        registry = HookRegistry()
        hook = LoggingHook()
        registry.register(hook)
        hooks = registry.get_hooks(HookPhase.PRE_COMMAND)
        assert len(hooks) >= 1

    def test_register_class(self) -> None:
        registry = HookRegistry()
        registry.register_class(LoggingHook)
        hooks = registry.get_hooks(HookPhase.PRE_COMMAND)
        assert len(hooks) >= 1

    def test_get_all_hooks(self) -> None:
        registry = HookRegistry.with_defaults()
        all_hooks = registry.get_all_hooks()
        assert HookPhase.PRE_COMMAND in all_hooks

    def test_with_defaults_populates_builtins(self) -> None:
        registry = HookRegistry.with_defaults()
        hooks = registry.get_hooks(HookPhase.PRE_COMMAND)
        assert any(isinstance(h, LoggingHook) for h in hooks)
        assert any(isinstance(h, TimingHook) for h in hooks)

    def test_sort_by_priority(self) -> None:
        registry = HookRegistry()
        h1 = LoggingHook()  # priority 50
        h2 = TimingHook()   # priority 10
        registry.register(h1)
        registry.register(h2)
        hooks = registry.get_hooks(HookPhase.PRE_COMMAND)
        assert hooks[0].priority <= hooks[1].priority

class TestHookExecutor:
    @pytest.mark.asyncio
    async def test_execute_phase_no_hooks(self) -> None:
        HookRegistry._hooks = {}
        HookRegistry._initialized = True
        executor = HookExecutor()
        ctx = await executor.execute_phase(HookPhase.POST_COMMAND, HookContext())
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_pre_command(self) -> None:
        HookRegistry._hooks = {}
        HookRegistry._initialized = False
        executor = HookExecutor()
        ctx = await executor.pre_command("test", (1,), {"a": 2})
        assert ctx.command == "test"

    @pytest.mark.asyncio
    async def test_post_command(self) -> None:
        HookRegistry._hooks = {}
        HookRegistry._initialized = False
        executor = HookExecutor()
        ctx = await executor.post_command(HookContext(), "result")
        assert ctx.result == "result"

    @pytest.mark.asyncio
    async def test_on_error(self) -> None:
        HookRegistry._hooks = {}
        HookRegistry._initialized = False
        executor = HookExecutor()
        ctx = await executor.on_error(HookContext(), ValueError("fail"))
        assert ctx.error is not None


class TestCreateValidationHook:
    @pytest.mark.asyncio
    async def test_validation_passes(self) -> None:
        h = create_validation_hook("my_validator", lambda ctx: True)
        assert h.name == "my_validator"
        result = await h.execute(HookContext())
        assert result.success is True

    @pytest.mark.asyncio
    async def test_validation_fails(self) -> None:
        h = create_validation_hook("my_validator", lambda ctx: False)
        result = await h.execute(HookContext())
        assert result.success is False
