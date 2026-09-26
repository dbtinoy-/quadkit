"""Event handler generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class EventHandlerGenerator(GeneratorBase):
    """Generate an event handler with bus registration.

    The emitted handler follows the convention demonstrated in
    ``examples/event-driven-orders``: ``on_<event_type>`` methods that the
    event bus subscribes to explicitly during provider boot. The subscribed
    event is a separate input from the handler's own name — pass ``event``
    when they differ, or the handler name is used for both (the standalone
    case, where the two are the same word).
    """

    name = "event_handler"
    description = "Generate an event handler with bus registration"
    default_output_dir = "src/handlers"

    def __init__(self, output_dir: str | Path = "src/handlers") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        event: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an event handler module.

        Args:
            name: Handler name, e.g. ``"OrderPlaced"`` or ``"order_placed"``.
            event: Name of the event this handler subscribes to, e.g.
                ``"order_created"``. Defaults to *name*: a handler whose
                subscription is not named after itself (``SendConfirmation``
                subscribing to ``order_created``) must say so, because the
                method and the ``event_name`` log attribute both describe the
                event, not the handler.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        handler_name = self._to_pascal_case(name)
        handler_snake = self._to_snake_case(name)
        event_snake = self._to_snake_case(event) if event else handler_snake
        context: dict[str, Any] = {
            "handler_name": handler_name,
            "handler_snake": handler_snake,
            "event_name": event_snake,
        }
        content = self.render_template("event_handler.py.jinja2", context)
        file_path = self.output_dir / f"{handler_snake}_handler.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["EventHandlerGenerator"]
