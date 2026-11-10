"""Workflow module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.workflow import (
    ContentCheckpointStoreProtocol,
    PipelineProtocol,
    SagaStoreProtocol,
    StateMachineProtocol,
)
from quadkit.di.module import DynamicModule, Module, module
from quadkit.workflow.config import ContentCheckpointConfig
from quadkit.workflow.di.provider import WorkflowProvider

if TYPE_CHECKING:
    from quadkit.workflow.config import BulkOperationConfig


@module()
class WorkflowModule(Module):
    """Pipeline orchestration, bulk operations, saga state machines, and graph engine.

    Call :meth:`configure` to configure the workflow subsystem.

    Usage (defaults)::

        @module(imports=[WorkflowModule.configure()])
        class AppModule(Module):
            pass

    Usage (configured)::

        from quadkit.workflow.config import BulkOperationConfig

        @module(
            imports=[WorkflowModule.configure(BulkOperationConfig(batch_size=200))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        config: BulkOperationConfig | None = None,
        saga_store: SagaStoreProtocol | None = None,
        state_machine: StateMachineProtocol | None = None,
        content_checkpoint_store: ContentCheckpointStoreProtocol | None = None,
        content_checkpoint_config: ContentCheckpointConfig | None = None,
    ) -> DynamicModule:
        """Create a WorkflowModule with explicit configuration.

        Args:
            config: :class:`~quadkit.workflow.config.BulkOperationConfig` or ``None``
                for framework defaults.
            saga_store: Optional durable :class:`~quadkit.contracts.workflow.SagaStoreProtocol`
                implementation.  Defaults to in-memory.
            state_machine: Optional application-configured
                :class:`~quadkit.contracts.workflow.StateMachineProtocol` to
                register for DI consumers.
            content_checkpoint_store: Optional :class:`~quadkit.contracts.workflow.ContentCheckpointStoreProtocol`
                implementation for content-addressed saga checkpoints.
            content_checkpoint_config: Optional :class:`~quadkit.workflow.config.ContentCheckpointConfig`
                governing inline-output threshold and TTL.  When omitted,
                framework defaults are used (1 MiB inline, 24 h TTL).

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.workflow.config import BulkOperationConfig

        if config is not None and not isinstance(config, BulkOperationConfig):
            raise TypeError(
                f"config must be BulkOperationConfig, got {type(config).__name__}"
            )
        if content_checkpoint_config is not None and not isinstance(
            content_checkpoint_config, ContentCheckpointConfig
        ):
            raise TypeError(
                "content_checkpoint_config must be ContentCheckpointConfig, "
                f"got {type(content_checkpoint_config).__name__}"
            )

        return DynamicModule(
            module=cls,
            providers=[
                WorkflowProvider(
                    config=config,
                    saga_store=saga_store,
                    state_machine=state_machine,
                    content_checkpoint_store=content_checkpoint_store,
                    content_checkpoint_config=content_checkpoint_config,
                )
            ],
            exports=[
                PipelineProtocol,
                *([StateMachineProtocol] if state_machine is not None else []),
            ],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return an in-memory WorkflowModule for unit testing.

        Uses in-memory saga store and default workflow configuration.
        No external state backends are required.

        Returns:
            A DynamicModule with in-memory workflow state.
        """
        return DynamicModule(
            module=cls,
            providers=[WorkflowProvider()],
            exports=[PipelineProtocol],
        )


__all__ = ["WorkflowModule"]
