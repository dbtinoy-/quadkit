"""Controller generator."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen import GenerationResult, GeneratorBase, parse_fields
from quadkit.contracts.cli.generators import resolve_options

#: CRUD operations a generated controller can expose.
CONTROLLER_OPS: tuple[str, ...] = ("create", "get", "list", "update", "delete")


def _contract_errors(ops: dict[str, bool]) -> list[str]:
    """Return the contracts exception symbols the rendered controller needs.

    Keeping the import list derived from the selected operations avoids
    emitting unused imports (and the lint failures that follow) when a
    controller is generated with a reduced operation set. Handlers return
    ``Result[T, E]`` over these domain errors (Convention: Result +
    ProblemDetail); ``DomainError`` is the base of the controller's
    request-shape error, ``NotFoundError`` the missing-row error.

    Args:
        ops: Resolved per-operation render flags.

    Returns:
        Sorted-by-declaration exception names to import from
        ``quadkit.contracts.exceptions``; empty when none are required.
    """
    needed: list[str] = []
    if ops["create"] or ops["update"]:
        needed.append("DomainError")
    if ops["list"] or ops["get"] or ops["update"] or ops["delete"]:
        # list signs its envelope Result[..., NotFoundError] too (2026-10-21,
        # owner): one return shape per controller, and a future failing arm
        # lands where the type already points.
        needed.append("NotFoundError")
    return needed


class ControllerGenerator(GeneratorBase):
    """Generate a controller class with CRUD endpoints.

    By default every CRUD handler is rendered. Pass ``ops`` to emit a subset —
    either a comma-separated string (``"create,get,list"``) or any iterable of
    operation names. Unknown names are rejected so a typo fails loudly instead
    of silently producing an empty controller.
    """

    def __init__(self, output_dir: str | Path = "src/controllers") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        path: str | None = None,
        doc: str | None = None,
        ops: str | list[str] | tuple[str, ...] | set[str] | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        name = self._strip_type_suffix(name, "Controller")
        model_name = self._to_snake_case(name)
        resource_name = self._pluralize(model_name)
        api_path = path or f"/{resource_name}"
        fields = parse_fields(fields_str or "")
        selected_ops = self._normalize_ops(ops)
        file_path = self.output_dir / f"{model_name}_controller.py"
        content = self.render_template(
            "controller.py.jinja2",
            {
                "class_name": self._to_pascal_case(name),
                "model_name": model_name,
                "resource_name": resource_name,
                "resource_path": api_path.strip("/"),
                "doc": doc,
                "ops": selected_ops,
                "ops_enabled": [op for op in CONTROLLER_OPS if selected_ops[op]],
                "write_ops": bool(selected_ops["create"] or selected_ops["update"]),
                "contract_errors": _contract_errors(selected_ops),
                # 2026-10-21 (owner): including `list` — every HTTP verb is
                # Result-shaped, so every controller imports the toolkit.
                "needs_result": any(selected_ops.values()),
                # Sibling component packages differ by project structure:
                # ``repositories`` in structured layouts, ``app.repositories``
                # in minimal ones, ``app.modules.<feature>.repositories`` in
                # modular ones.
                "repository_module": self._sibling_package(
                    self.output_dir, "repositories"
                ),
                "models_module": self._sibling_package(self.output_dir, "domains"),
                "required_fields": [field.name for field in fields if field.required],
                "fields": [
                    {
                        "name": field.name,
                        "type": field.type,
                        "required": field.required,
                    }
                    for field in fields
                ],
            },
        )
        # Conditional blocks leave trailing blank lines whenever the last
        # operation is not rendered; normalise to exactly one trailing
        # newline so every ops combination is framed identically.
        self.stage(file_path, content.rstrip() + "\n")
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _normalize_ops(
        ops: str | list[str] | tuple[str, ...] | set[str] | None,
    ) -> dict[str, bool]:
        """Resolve the requested operations into per-op render flags.

        Args:
            ops: Comma-separated string, iterable of names, or ``None`` for
                the full CRUD set.

        Returns:
            Mapping of every supported operation to whether it is rendered.

        Raises:
            ValueError: If an unknown operation name is requested.
        """
        if ops is None:
            return dict.fromkeys(CONTROLLER_OPS, True)

        if isinstance(ops, str):
            requested = [part.strip() for part in ops.split(",") if part.strip()]
        else:
            requested = [str(part).strip() for part in ops if str(part).strip()]

        unknown = sorted(set(requested) - set(CONTROLLER_OPS))
        if unknown:
            raise ValueError(
                f"Unknown controller ops {unknown}; "
                f"expected any of {list(CONTROLLER_OPS)}"
            )
        chosen = set(requested)
        return {op: op in chosen for op in CONTROLLER_OPS}

    @staticmethod
    def _strip_type_suffix(name: str, suffix: str) -> str:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
        return name

    @staticmethod
    def _pluralize(value: str) -> str:
        if value.endswith("y") and value[-2:-1] not in {"a", "e", "i", "o", "u"}:
            return f"{value[:-1]}ies"
        if value.endswith("s"):
            return value
        return f"{value}s"


__all__ = ["CONTROLLER_OPS", "ControllerGenerator"]
