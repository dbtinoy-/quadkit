"""MCPController generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen.base import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class MCPControllerGenerator(GeneratorBase):
    """Generate an MCPController class with @tool, @resource, and @prompt examples.

    Usage::

        quadkit gen mcp-controller DataTools

    This creates ``data_tools_controller.py`` in the output directory
    containing a fully-annotated ``DataToolsController(MCPController)`` class
    with example implementations for all three MCP primitives.
    """

    name = "mcp-controller"
    description = "Generate an MCP controller with tools, resources, and prompts"
    default_output_dir = "src/mcp"

    def __init__(self, output_dir: str | Path = "src/mcp") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an MCPController file.

        Args:
            name: Controller name, e.g. ``"DataTools"`` or ``"user_service"``.
                  File name is derived from this.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        module_name = self._to_snake_case(name).removesuffix("_controller")
        class_name = self._to_pascal_case(module_name)
        # Strip trailing "Controller" from the class name if present
        if class_name.endswith("Controller"):
            class_name = class_name[: -len("Controller")]

        # Build a URI-friendly resource name (simple pluralisation)
        resource_name = module_name.replace("_", " ")
        if not resource_name.endswith("s"):
            resource_name += "s"

        context: dict[str, Any] = {
            "class_name": class_name,
            "module_name": module_name,
            "tool_prefix": module_name,
            "resource_name": resource_name,
            "resource_uri": f"{module_name}://",
        }

        content = self.render_template("mcp_controller.py.jinja2", context)
        file_path = self.output_dir / f"{module_name}_controller.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["MCPControllerGenerator"]
