"""ValidationPhase — verify every module import resolves to a known module."""

from __future__ import annotations

from quadkit.contracts.exceptions.provider import ModuleImportError
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.errors import format_missing_import_error


class ValidationPhase:
    """Phase 3: Validate that every declared import is present in the graph.

    After :class:`CollectPhase` and :class:`CycleDetectionPhase`, each
    node's import list must reference a module that was actually collected.
    Missing imports raise :exc:`ModuleImportError`.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Check all import references in ``ctx.nodes``.

        Args:
            ctx: Shared compilation state.  Reads ``nodes`` only.

        Raises:
            ModuleImportError: If any import references a module not in the graph.
        """
        available_names = [node.name for node in ctx.nodes.values()]

        for node in ctx.nodes.values():
            for imp_cls in node.imports:
                if imp_cls not in ctx.nodes:
                    imp_name = (
                        imp_cls.__name__ if isinstance(imp_cls, type) else repr(imp_cls)
                    )
                    raise ModuleImportError(
                        format_missing_import_error(
                            module_name=node.name,
                            missing_name=imp_name,
                            available=available_names,
                        ),
                        module_name=node.name,
                        missing_import=imp_name,
                        available_modules=available_names,
                        hint=(
                            f"Register {imp_name} with app.add_module(), or remove it "
                            f"from {node.name}.imports."
                        ),
                    )
