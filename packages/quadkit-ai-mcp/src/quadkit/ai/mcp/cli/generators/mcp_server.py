"""MCP server script generator (Gear 1 — standalone script-mode)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen.base import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class MCPServerGenerator(GeneratorBase):
    """Generate a standalone MCP server script with module-level decorators.

    Usage::

        quadkit gen mcp-server data_tools

    This creates ``data_tools_tools.py`` (script-mode Gear 1) with
    ``@tool``, ``@resource``, and ``@prompt`` decorated functions plus a
    ``__main__`` block so the file is directly executable::

        python data_tools_tools.py
        # — or —
        quadkit mcp serve data_tools_tools.py
    """

    name = "mcp-server"
    description = "Generate a standalone MCP server script"
    default_output_dir = "src"

    def __init__(self, output_dir: str | Path = "src") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a standalone MCP server script.

        Args:
            name: Base name for the server / module, e.g. ``"data_tools"``.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        module_name = self._to_snake_case(name).removesuffix("_tools")

        # Build a URI-friendly resource name (simple pluralisation)
        resource_name = module_name.replace("_", " ")
        if not resource_name.endswith("s"):
            resource_name += "s"

        context: dict[str, Any] = {
            "module_name": module_name,
            "tool_prefix": module_name,
            "resource_name": resource_name,
            "resource_uri": f"{module_name}://",
        }
        content = self.render_template("mcp_server.py.jinja2", context)
        file_path = self.output_dir / f"{module_name}_tools.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["MCPServerGenerator"]
