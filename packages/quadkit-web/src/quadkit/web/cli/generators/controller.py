"""Controller generator."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen import (
    EntitySpec,
    GenerationResult,
    GeneratorBase,
    pluralize_identifier,
    resolve_field_specs,
)
from quadkit.contracts.cli.generators import resolve_options

#: CRUD operations a generated controller can expose.
CONTROLLER_OPS: tuple[str, ...] = ("create", "get", "list", "update", "delete")


def _contract_errors(
    ops: dict[str, bool], *, principal: bool = False, validator: bool = False
) -> list[str]:
    """Return the contracts exception symbols the rendered controller needs.

    Keeping the import list derived from the selected operations avoids
    emitting unused imports (and the lint failures that follow) when a
    controller is generated with a reduced operation set. Handlers return
    ``Result[T, E]`` over these domain errors (Convention: Result +
    ProblemDetail); ``DomainError`` is the base of the controller's
    request-shape error, ``NotFoundError`` the missing-row error, and
    ``ConflictError``/``ValidationError`` the repository's integrity
    outcomes on write verbs. Two feature flags widen the set:
    ``principal`` (a principal-assigned create fails closed with
    ``AuthenticationError`` when no authenticated subject is present)
    and ``validator`` (enforced validator failures travel as
    ``ValidationError`` carrying per-field ``FieldError`` values).

    Args:
        ops: Resolved per-operation render flags.
        principal: Whether the rendered create injects the authenticated
            principal into principal-assigned fields.
        validator: Whether the rendered write handlers enforce a wired
            validator function.

    Returns:
        Sorted-by-declaration exception names to import from
        ``quadkit.contracts.exceptions``; empty when none are required.
    """
    needed: list[str] = []
    if principal and ops["create"]:
        needed.append("AuthenticationError")
    if ops["create"] or ops["update"] or ops["delete"]:
        # Write verbs sign the repository's integrity arm: a restricted
        # delete or unique collision answers 409 as ``ConflictError``.
        needed.append("ConflictError")
    if ops["create"] or ops["update"]:
        needed.append("DomainError")
    if validator and (ops["create"] or ops["update"]):
        needed.append("FieldError")
    if any(ops.values()):
        # Every repository verb now signs the not-found arm, including the
        # normally infallible create/list pair, so any rendered handler can
        # name the error its repository returns.
        needed.append("NotFoundError")
    if ops["create"] or ops["update"]:
        # A create/update that references a missing row answers 422 as
        # the contracts ``ValidationError``. It is aliased on import:
        # the same module imports pydantic's ``ValidationError`` for
        # request-body parsing, and one name cannot bind both.
        needed.append("ValidationError as DomainValidationError")
    return needed


def _dto_imports(class_name: str, ops: dict[str, bool]) -> list[str]:
    """Return entity documentation and write DTO symbols used by this subset.

    Create and update are independently selectable operations. Deriving
    the model import from those flags keeps an append-only controller
    from importing its unused ``Update`` DTO (and an update-only one
    from importing ``Create``), which otherwise fails the generated
    project's own unused-import lint.
    """
    imports: list[str] = (
        [class_name]
        if any(ops[op] for op in ("create", "get", "list", "update"))
        else []
    )
    if ops["create"]:
        imports.append(f"{class_name}Create")
    if ops["update"]:
        imports.append(f"{class_name}Update")
    return imports


def _result_errors(class_name: str, *, principal: bool) -> dict[str, list[str]]:
    """Names of the native Result error arms declared by each CRUD handler."""
    write_errors = ["ConflictError", "DomainValidationError", "NotFoundError"]
    return {
        "create": [
            f"Invalid{class_name}Error",
            *(["AuthenticationError"] if principal else []),
            *write_errors,
        ],
        "update": [f"Invalid{class_name}Error", *write_errors],
        "get": ["NotFoundError"],
        "list": ["NotFoundError"],
        "delete": ["ConflictError", "NotFoundError"],
    }


def _result_imports(ops: dict[str, bool]) -> list[str]:
    """Return the ``quadkit.result`` symbols the rendered controller uses.

    Repository handlers only *map* a ``Result``; ``Ok``/``Err`` are
    constructed solely by the request-body helper rendered for write
    operations. Deriving the list keeps read-only subsets free of unused
    imports under a generated project's own Ruff configuration.
    """
    if not any(ops.values()):
        return []
    if ops["create"] or ops["update"]:
        return ["Err", "Ok", "Result"]
    return ["Result"]


class ControllerGenerator(GeneratorBase):
    """Generate a controller class with CRUD endpoints.

    By default every CRUD handler is rendered. Pass ``ops`` to emit a subset —
    either a comma-separated string (``"create,get,list"``) or any iterable of
    operation names. Unknown names are rejected so a typo fails loudly instead
    of silently producing an empty controller.

    Two entity/option-driven behaviours ride the same render. A field
    marked ``principal_assigned`` on the entity spec is injected from the
    authenticated request on create (and fails closed without one), so
    ownership subjects can never be spoofed through a request body. The
    ``validator_module``/``validator_function`` options name a
    ``validate_<entity>_payload(data) -> dict[str, str]`` function the
    write handlers enforce after DTO validation, before the repository
    write; failures answer 422 with per-field errors.
    """

    supports_entity_spec = True

    def __init__(self, output_dir: str | Path = "src/controllers") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        entity_spec: EntitySpec | None = None,
        path: str | None = None,
        doc: str | None = None,
        ops: str | list[str] | tuple[str, ...] | set[str] | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        name = self._strip_type_suffix(name, "Controller")
        model_name = self._to_snake_case(name)
        if (
            entity_spec is not None
            and self._to_snake_case(entity_spec.name) != model_name
        ):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        resource_name = (
            entity_spec.table_name
            if entity_spec is not None
            else self._pluralize(model_name)
        )
        api_path = path or f"/{resource_name}"
        fields = resolve_field_specs(fields_str, entity_spec)
        selected_ops = self._normalize_ops(ops)
        # Principal-assigned ownership fields: the rendered create injects
        # the authenticated subject after DTO validation (the fields are
        # absent from the write DTOs, so a request body cannot spoof
        # them). Meaningful only when a create handler is rendered.
        principal_fields = (
            [field.name for field in fields if field.principal_assigned]
            if selected_ops["create"]
            else []
        )
        # Validator enforcement: the caller names the payload-validator
        # module/function pair (``validate_<entity>_payload`` returning a
        # ``{field: message}`` dict); the rendered write handlers call it
        # after DTO validation and before the repository write. The pair
        # is both-or-neither, and renders only with a write handler so a
        # read-only controller never imports an unused validator.
        validator_module = str(options.get("validator_module") or "")
        validator_function = str(options.get("validator_function") or "")
        if bool(validator_module) != bool(validator_function):
            raise ValueError(
                "validator_module and validator_function must be passed together"
            )
        if not (selected_ops["create"] or selected_ops["update"]):
            validator_module = ""
            validator_function = ""
        file_path = self.output_dir / f"{model_name}_controller.py"
        class_name = self._to_pascal_case(name)
        content = self.render_template(
            "controller.py.jinja2",
            {
                "class_name": class_name,
                "model_name": model_name,
                "resource_name": resource_name,
                "resource_path": api_path.strip("/"),
                "doc": doc,
                "ops": selected_ops,
                "ops_enabled": [op for op in CONTROLLER_OPS if selected_ops[op]],
                "write_ops": bool(selected_ops["create"] or selected_ops["update"]),
                "dto_imports": _dto_imports(class_name, selected_ops),
                "result_errors": _result_errors(
                    class_name, principal=bool(principal_fields)
                ),
                "principal_fields": principal_fields,
                # Row serialization needs declared types: generic JSON encoding
                # cannot distinguish SQL naive UTC from arbitrary user strings.
                "datetime_fields": (
                    tuple(field.name for field in fields if field.type == "datetime")
                    if any(
                        selected_ops[op] for op in ("create", "get", "list", "update")
                    )
                    else ()
                ),
                "validator_module": validator_module,
                "validator_function": validator_function,
                "contract_errors": _contract_errors(
                    selected_ops,
                    principal=bool(principal_fields),
                    validator=bool(validator_module),
                ),
                # Every HTTP verb is Result-shaped; only the body helper
                # constructs Ok/Err, so derive exactly the used symbols.
                "result_imports": _result_imports(selected_ops),
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
        return pluralize_identifier(value)


__all__ = ["CONTROLLER_OPS", "ControllerGenerator"]
