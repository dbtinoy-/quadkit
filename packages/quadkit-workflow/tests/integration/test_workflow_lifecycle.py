"""Integration tests for the quadkit-workflow provider lifecycle.

Tests the complete DI lifecycle for the workflow subsystem using the real
Container — no external services required.

Flow under test:
  WorkflowProvider.register() → WorkflowProvider.boot()
  → resolve BulkOperationConfig → resolve WorkflowProvider (self-ref)
  → TransformPipe end-to-end execution → WorkflowProvider.shutdown()
"""

from __future__ import annotations

import pytest

from quadkit.di.container import Container
from quadkit.workflow.config import BulkOperationConfig
from quadkit.workflow.core.pipe import TransformPipe
from quadkit.workflow.di.provider import WorkflowProvider

pytestmark = [pytest.mark.integration]


class TestWorkflowProviderLifecycle:
    """Full provider lifecycle for the workflow subsystem.

    Exercises the register → boot → resolve → end-to-end pipe execution
    → shutdown sequence using the real DI Container.
    """

    @pytest.fixture
    async def booted_container(self):
        """Container with WorkflowProvider fully registered and booted."""
        provider = WorkflowProvider(config=BulkOperationConfig(batch_size=50))
        container = Container()
        await provider.register(container)
        await provider.boot(container)
        yield container
        await provider.shutdown()

    # ------------------------------------------------------------------
    # register phase
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_register_binds_bulk_operation_config(self) -> None:
        """BulkOperationConfig singleton is bound after register()."""
        provider = WorkflowProvider(config=BulkOperationConfig(batch_size=10))
        container = Container()

        await provider.register(container)

        config = await container.resolve(BulkOperationConfig)

        assert isinstance(config, BulkOperationConfig)
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_register_binds_provider_self_reference(self) -> None:
        """WorkflowProvider self-reference is resolvable after register()."""
        provider = WorkflowProvider()
        container = Container()

        await provider.register(container)

        resolved_provider = await container.resolve(WorkflowProvider)

        assert resolved_provider is provider
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_register_reflects_custom_config_values(self) -> None:
        """Custom BulkOperationConfig values are preserved in the container."""
        custom_config = BulkOperationConfig(
            batch_size=200,
            max_concurrency=8,
            timeout=30.0,
        )
        provider = WorkflowProvider(config=custom_config)
        container = Container()

        await provider.register(container)

        config = await container.resolve(BulkOperationConfig)

        assert config.batch_size == 200
        assert config.max_concurrency == 8
        assert config.timeout == 30.0
        await provider.shutdown()

    # ------------------------------------------------------------------
    # boot phase
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_boot_completes_without_error(
        self, booted_container: Container
    ) -> None:
        """boot() resolves BulkOperationConfig and logs without raising."""
        config = await booted_container.resolve(BulkOperationConfig)

        assert config is not None

    @pytest.mark.asyncio
    async def test_singleton_returns_same_config_instance(
        self, booted_container: Container
    ) -> None:
        """Resolving BulkOperationConfig twice returns the same singleton."""
        config_a = await booted_container.resolve(BulkOperationConfig)
        config_b = await booted_container.resolve(BulkOperationConfig)

        assert config_a is config_b

    @pytest.mark.asyncio
    async def test_boot_with_default_config_succeeds(self) -> None:
        """WorkflowProvider boots successfully with all-defaults configuration."""
        provider = WorkflowProvider()
        container = Container()

        await provider.register(container)
        await provider.boot(container)

        config = await container.resolve(BulkOperationConfig)

        assert config.batch_size == 10  # framework default
        await provider.shutdown()

    # ------------------------------------------------------------------
    # TransformPipe end-to-end
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_transform_pipe_executes_sync_steps_in_order(self) -> None:
        """TransformPipe correctly chains synchronous transformation steps."""
        execution_log: list[str] = []

        def step_add_ten(value: int) -> int:
            execution_log.append("add_ten")
            return value + 10

        def step_double(value: int) -> int:
            execution_log.append("double")
            return value * 2

        pipe: TransformPipe[int] = TransformPipe()
        result = await pipe.pipe(step_add_ten).pipe(step_double).execute(5)

        assert result == 30  # (5 + 10) * 2
        assert execution_log == ["add_ten", "double"]

    @pytest.mark.asyncio
    async def test_transform_pipe_executes_async_steps_in_order(self) -> None:
        """TransformPipe correctly chains async transformation steps."""

        async def async_upper(value: str) -> str:
            return value.upper()

        async def async_strip(value: str) -> str:
            return value.strip()

        pipe: TransformPipe[str] = TransformPipe()
        result = await pipe.pipe(async_strip).pipe(async_upper).execute("  hello world  ")

        assert result == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_transform_pipe_tap_does_not_alter_value(self) -> None:
        """tap() observes the value but does not change it."""
        observed: list[int] = []

        pipe: TransformPipe[int] = TransformPipe()
        result = await pipe.tap(observed.append).execute(42)

        assert result == 42
        assert observed == [42]

    @pytest.mark.asyncio
    async def test_transform_pipe_pipe_if_applies_step_when_predicate_true(
        self,
    ) -> None:
        """pipe_if() applies the step when the predicate returns True."""

        def double(value: int) -> int:
            return value * 2

        pipe: TransformPipe[int] = TransformPipe()
        result = await pipe.pipe_if(lambda v: v > 0, double).execute(5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_transform_pipe_pipe_if_skips_step_when_predicate_false(
        self,
    ) -> None:
        """pipe_if() passes the value through unchanged when predicate is False."""

        def double(value: int) -> int:
            return value * 2

        pipe: TransformPipe[int] = TransformPipe()
        result = await pipe.pipe_if(lambda v: v > 0, double).execute(-3)

        assert result == -3

    @pytest.mark.asyncio
    async def test_transform_pipe_catch_recovers_from_exception(self) -> None:
        """catch() handler intercepts an exception and returns a recovery value."""

        def explode(value: int) -> int:
            raise ValueError("intentional failure")

        def recover(exc: Exception, value: int) -> int:
            return -1

        pipe: TransformPipe[int] = TransformPipe()
        result = await pipe.pipe(explode).catch(recover).execute(99)

        assert result == -1

    @pytest.mark.asyncio
    async def test_transform_pipe_empty_returns_value_unchanged(self) -> None:
        """An empty TransformPipe returns the input value without modification."""
        pipe: TransformPipe[str] = TransformPipe()
        result = await pipe.execute("untouched")

        assert result == "untouched"

    # ------------------------------------------------------------------
    # shutdown
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self) -> None:
        """Calling shutdown() twice must not raise."""
        provider = WorkflowProvider()
        container = Container()
        await provider.register(container)
        await provider.boot(container)

        await provider.shutdown()
        await provider.shutdown()
