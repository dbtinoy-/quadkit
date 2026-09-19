"""CompilerPhase protocol — the contract for all compiler pipeline phases."""

from __future__ import annotations

from typing import Protocol

from quadkit.di.module.compiler.context import CompilerContext


class CompilerPhase(Protocol):
    """Protocol implemented by every phase in the :class:`ModuleCompiler` pipeline.

    Each phase reads from and writes to a shared :class:`CompilerContext`,
    transforming it in place.  Phases execute in the order returned by
    :meth:`ModuleCompiler._default_phases`.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Run this phase against the given compilation context.

        Args:
            ctx: The shared mutable state for this compilation run.
        """
        ...
