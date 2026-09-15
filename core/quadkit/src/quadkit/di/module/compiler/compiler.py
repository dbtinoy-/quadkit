"""ModuleCompiler — orchestrates the module compilation pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.compiler.phases.collect import CollectPhase
from quadkit.di.module.compiler.phases.detect_cycles import CycleDetectionPhase
from quadkit.di.module.compiler.phases.expand import ReexportExpansionPhase
from quadkit.di.module.compiler.phases.order import ProviderOrderingPhase
from quadkit.di.module.compiler.phases.validate import ValidationPhase
from quadkit.di.module.compiler.phases.visibility import VisibilityPhase
from quadkit.di.module.graph import CompiledModuleGraph
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.module.compiler.phases import CompilerPhase
    from quadkit.di.module.dynamic import DynamicModule

logger = get_logger(__name__)


class ModuleCompiler:
    """Compiles a module dependency graph into an execution plan.

    Transforms a flat list of module declarations into a fully validated,
    ordered execution plan by running a sequence of :class:`CompilerPhase`
    objects against a shared :class:`CompilerContext`.

    Usage::

        compiler = ModuleCompiler()
        graph = compiler.compile(
            root_modules=[CoreModule.configure(), AuthModule, BillingModule],
            standalone_providers=[MetricsProvider()],
        )
        # graph.provider_order → ordered list of ProviderEntry
        # graph.visibility    → per-module visibility sets

    Custom phases can be injected for testing or extension::

        compiler = ModuleCompiler(phases=[CollectPhase(), MyCustomPhase()])
    """

    def __init__(self, phases: list[CompilerPhase] | None = None) -> None:
        """Initialise the compiler with an optional custom phase pipeline.

        Args:
            phases: Ordered list of phases to execute during compilation.
                Defaults to the standard six-phase pipeline when ``None``.
        """
        self._phases: list[CompilerPhase] = phases or self._default_phases()

    @staticmethod
    def _default_phases() -> list[CompilerPhase]:
        """Build the standard six-phase compilation pipeline.

        Returns:
            Ordered list of :class:`CompilerPhase` instances.
        """
        return [
            CollectPhase(),
            CycleDetectionPhase(),
            ValidationPhase(),
            ReexportExpansionPhase(),
            VisibilityPhase(),
            ProviderOrderingPhase(),
        ]

    def compile(
        self,
        root_modules: list[type | DynamicModule],
        standalone_providers: list[Any] | None = None,
    ) -> CompiledModuleGraph:
        """Compile the module graph.

        Args:
            root_modules: Module classes and/or :class:`DynamicModule`
                instances registered via ``app.add_module()``.
            standalone_providers: Provider instances added via
                ``app.add_provider()``.  These are appended to the
                provider order after all module providers.

        Returns:
            A :class:`CompiledModuleGraph` ready for the orchestrator.

        Raises:
            ModuleCycleError: Circular import detected.
            ModuleImportError: Imported module not in graph.
            ModuleDuplicateError: Same module with conflicting configs.
            ModuleError: Any other structural issue.
        """
        ctx = CompilerContext(
            root_modules=root_modules,
            standalone_providers=standalone_providers or [],
        )

        for phase in self._phases:
            phase.execute(ctx)

        self._check_stub_requirements(ctx)

        graph = CompiledModuleGraph(
            nodes=ctx.nodes,
            provider_order=ctx.provider_order,
            visibility=ctx.visibility,
            global_exports=ctx.global_exports,
            warnings=list(ctx.warnings),
        )

        logger.info(
            "compiler.complete",
            modules=len(graph.nodes),
            providers=len(graph.provider_order),
            global_exports=len(graph.global_exports),
            warnings=len(graph.warnings),
        )

        return graph

    def _check_stub_requirements(self, ctx: CompilerContext) -> None:
        """Warn when ``require_stub=True`` modules have no ``stub()`` override.

        Checks each module's metadata for the ``require_stub`` flag.  If set,
        verifies that the module class has overridden the ``stub()`` classmethod
        from the base :class:`~quadkit.di.module.base.Module` class.  Appends
        a warning to ``ctx.warnings`` when the requirement is not met.

        Args:
            ctx: Shared compilation state.  Reads ``nodes``; appends to
                ``warnings``.
        """
        from quadkit.di.module.base import Module
        from quadkit.di.module.constants import MODULE_METADATA_ATTR

        for cls, node in ctx.nodes.items():
            meta = getattr(cls, MODULE_METADATA_ATTR, None)
            if meta is None or not meta.require_stub:
                continue

            stub_method = getattr(cls, "stub", None)
            if stub_method is None:
                continue

            if getattr(stub_method, "__func__", None) is getattr(
                Module.stub, "__func__", None
            ):
                ctx.warnings.append(
                    f"Module '{node.name}' has require_stub=True but does not "
                    f"override stub(). Tests using this module should import "
                    f"and call {cls.__name__}.stub() instead of "
                    f"{cls.__name__}.configure()."
                )
