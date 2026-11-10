"""Event handler generator."""

from __future__ import annotations

from keyword import iskeyword
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
    supports_use_case_binding_v1 = True

    def __init__(self, output_dir: str | Path = "src/handlers") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        event: str | None = None,
        use_case: dict[str, Any] | None = None,
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
            use_case: Optional explicit internal event-to-use-case binding. It names
                module/command/result/event_module/event_class and same-name inputs.
                The existing command handler must validate inputs and enforce behavior;
                this adapter supplies no user principal, clock or authorization.
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
        template = "event_handler.py.jinja2"
        if use_case is not None:
            context.update(self._compile_use_case(use_case))
            template = "event_use_case_handler.py.jinja2"
        content = self.render_template(template, context)
        file_path = self.output_dir / f"{handler_snake}_handler.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _compile_use_case(spec: dict[str, Any]) -> dict[str, Any]:
        """Explicit internal-event binding; no expressions or authority mapping."""
        if type(spec) is not dict or set(spec) != {
            "module",
            "command",
            "result",
            "event_module",
            "event_class",
            "inputs",
        }:
            raise ValueError(
                "use_case requires an exact event/command/result/input binding"
            )
        for key in ("module", "command", "result", "event_module", "event_class"):
            value = spec[key]
            parts = value.split(".") if type(value) is str else []
            if (
                not parts
                or (key not in {"module", "event_module"} and len(parts) != 1)
                or any(
                    not part.isascii()
                    or not part.isidentifier()
                    or iskeyword(part)
                    or part.startswith("_")
                    for part in parts
                )
            ):
                raise ValueError(
                    "use_case binding requires public Python import identifiers"
                )
        inputs = spec["inputs"]
        reserved = {
            "id",
            "timestamp",
            "metadata",
            "aggregate_id",
            "principal_sub",
            "clock",
            "actor_id",
        }
        if (
            type(inputs) is not list
            or any(
                type(name) is not str
                or not name.isascii()
                or not name.isidentifier()
                or iskeyword(name)
                or name.startswith("_")
                or name in reserved
                for name in inputs
            )
            or len(set(inputs)) != len(inputs)
        ):
            raise ValueError(
                "use_case inputs require unique public payload names without authority fields"
            )
        return {"binding": dict(spec)}


__all__ = ["EventHandlerGenerator"]
