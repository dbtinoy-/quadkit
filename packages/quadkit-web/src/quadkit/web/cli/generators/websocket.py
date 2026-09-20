"""WebSocket handler generator for the web package."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class WebSocketHandlerGenerator(GeneratorBase):
    """Generate a WebSocket handler scaffold."""

    name = "websocket"
    description = "Generate a WebSocket handler for real-time communication"
    default_output_dir = "src/websocket"

    def __init__(self, output_dir: str | Path = "src/websocket") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        """Generate a WebSocket handler module.

        Args:
            name: Handler name (e.g. ``"ChatSocket"`` or ``"chat_socket"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        snake_name = self._to_snake_case(name)
        file_path = self.output_dir / f"{snake_name}.py"
        content = self.render_template(
            "websocket.py.jinja2",
            {
                "name": self._to_pascal_case(name),
                "snake_name": snake_name,
                "snake_name_plural": f"{snake_name}s",
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["WebSocketHandlerGenerator"]
