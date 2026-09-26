"""Task generator for the Quadkit CLI."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any

from quadkit.codegen import (
    FieldSpec,
    GenerationResult,
    GeneratorBase,
    annotation_for,
    parse_fields,
)
from quadkit.contracts.cli.generators import resolve_options


class TaskGenerator(GeneratorBase):
    """Generate a background task."""

    name = "task"
    description = "Generate a background task with queue registration"
    default_output_dir = "src/tasks"
    template_name = "task.py.jinja2"

    def __init__(self, output_dir: str | Path = "src/tasks") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a task file.

        Args:
            name: The name of the task (e.g. ``"ProcessData"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        fields_str: str | None = options.get("fields_str")
        params_str: str | None = options.get("params_str")
        doc: str | None = options.get("doc")
        schedule: str | None = options.get("schedule")
        package_name: str = str(options.get("package_name", "app"))

        task_name = self._to_snake_case(name)
        fields = parse_fields(fields_str or "")

        params = self._parse_params(params_str or "")

        context: dict[str, Any] = {
            "name": name,
            "class_name": self._to_pascal_case(name),
            "task_name": task_name,
            "resource_name": task_name,
            "doc": doc,
            "schedule": schedule,
            "package_name": package_name,
            # A task runner with no parameters at all is not a useful
            # example, so one is shown. Its annotation matches its default:
            # ``int = None`` is an implicit optional, which is RUF013 in
            # ruff's default rule set — the exact complaint this template is
            # meant not to have.
            "params": params
            or [
                {
                    "name": "id",
                    "type": "int | None",
                    "default": "None",
                    "description": "The item ID",
                },
            ],
            "fields": [
                {"name": f.name, "type": f.type, "required": f.required} for f in fields
            ],
        }
        content = self.render_template(self.template_name, context)
        file_path = self.output_dir / f"{task_name}_task.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _parse_params(params_str: str) -> list[dict[str, str]]:
        """Parse ``name:type=default,...`` into param dicts.

        The declared shape is the field-spec shape every other generator
        accepts, so the parsing is delegated to ``parse_fields`` rather than
        re-implemented. It used to be re-implemented, and only split on ``=``:
        ``--params "batch_size:int=100"`` kept the type inside the *name* and
        emitted ``batch_size:int: Any = 100,``, a module that does not parse
        at all (tracker TASK-6).

        The older ``name=default`` spelling still works — a parameter without
        a type is a string — because that is what the option accepted before
        the type token was honoured, and it is in the generator's own tests.
        """
        parsed: list[FieldSpec] = []
        for raw_param in params_str.split(","):
            segment = raw_param.strip()
            if not segment:
                continue
            if ":" in segment.split("=", 1)[0]:
                parsed.extend(parse_fields(segment))
                continue
            name, _, default = segment.partition("=")
            name = name.strip()
            if not _UNTYPED_PARAM.match(segment):
                raise ValueError(
                    f"Invalid parameter specification: {segment!r} "
                    "(expected 'name:type=default')"
                )
            # No type token: the parameter is untyped, which is what this
            # generator produced before it honoured one. ``Any`` keeps that
            # promise instead of guessing a type from the default's spelling.
            parsed.append(
                FieldSpec(
                    name=name,
                    type="Any",
                    required=False,
                    default=default.strip() or None,
                )
            )
        params: list[dict[str, str]] = []
        for field in parsed:
            default = _render_default(field)
            params.append(
                {
                    "name": field.name,
                    "type": _annotation(field, default),
                    "default": default,
                    "description": f"The {field.name} parameter",
                }
            )
        return params


#: ``name`` or ``name=<default>`` — the option's pre-type spelling.
_UNTYPED_PARAM = re.compile(r"^(?P<name>[A-Za-z_]\w*)(?P<rest>\s*=.*)?$")

#: A bare word in a default is a *value*, not a name: ``name:str=hello`` means
#: the string "hello". Emitting it bare would raise NameError when the module
#: is imported, because default expressions are evaluated at definition time.
_BARE_WORD = re.compile(r"^[A-Za-z_]\w*$")


def _annotation(field: FieldSpec, default: str) -> str:
    """The parameter's annotation, widened when its default is ``None``.

    Every generated runner parameter has a default, so a parameter declared
    without one renders as ``= None``. Annotating that ``int = None`` is an
    implicit optional, which ruff reports as RUF013 in its default rule set —
    so the annotation says what the default means. ``Any`` needs no widening.
    """
    annotation = annotation_for(field.type)
    if default == "None" and annotation != "Any" and "| None" not in annotation:
        return f"{annotation} | None"
    return annotation


def _render_default(field: FieldSpec) -> str:
    """Render a parameter default as Python source.

    Literals (numbers, ``True``/``False``/``None``, quoted strings) pass
    through; a bare word is quoted, because the generator cannot know a name
    the generated module would have; anything else is left as written, so an
    expression such as ``datetime.now()`` or ``{}`` survives.
    """
    if field.default is None:
        return "None"
    text = field.default.strip()
    try:
        ast.literal_eval(text)
    except (ValueError, SyntaxError):
        if not _BARE_WORD.match(text):
            return text
        # A bare word is a string value. Double quotes because that is what
        # the formatter the generated project runs would choose.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


__all__ = ["TaskGenerator"]
