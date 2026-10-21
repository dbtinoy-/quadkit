"""Project-level metadata renderers shared by CLI and downstream builders.

These renderers are intentionally side-effect free. Consumers provide the
facts from the project they are creating; the renderer returns a deterministic
map of files to add to that project. The generated-app profile is separate
from any framework website or release metadata profile.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

__all__ = ["ProjectMetadataContext", "render_project_metadata"]


@dataclass(frozen=True, slots=True)
class ProjectMetadataContext:
    """Facts needed to render concise, project-specific agent instructions.

    Args:
        project_name: Human-facing project name.
        package_name: Importable Python package name.
        summary: Short project description.
        template_name: Scaffold/template identifier, not a release version.
        features: Framework features actually present in the generated project.
        dependencies: Direct requirements emitted into the project's manifest.
        layout: Existing important paths and their purpose, relative to project
            root. Paths must refer to this generated project, not the framework
            checkout.
        commands: Commands valid for the generated project and their purpose.
        notes: Project-specific operational notes, e.g. a generated dev secret
            must be replaced before deployment.
    """

    project_name: str
    package_name: str
    summary: str
    template_name: str
    features: tuple[str, ...]
    dependencies: tuple[str, ...]
    layout: tuple[tuple[str, str], ...]
    commands: tuple[tuple[str, str], ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject unsafe or malformed values before rendering Markdown."""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", self.project_name):
            raise ValueError("project_name must be a safe project slug")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.package_name):
            raise ValueError("package_name must be a Python package identifier")
        _require_single_line("summary", self.summary, allow_backticks=True)
        _require_single_line("template_name", self.template_name)
        for item in self.features:
            _require_single_line("feature", item)
        for item in self.dependencies:
            _require_single_line("dependency", item)
        if not self.summary.strip():
            raise ValueError("summary must not be empty")
        if not self.template_name.strip():
            raise ValueError("template_name must not be empty")
        if len(set(self.features)) != len(self.features):
            raise ValueError("features must not contain duplicates")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must not contain duplicates")
        for path, purpose in self.layout:
            _validate_project_path(path)
            _require_single_line("layout purpose", purpose, allow_backticks=True)
        for command, purpose in self.commands:
            _require_single_line("command", command)
            _require_single_line("command purpose", purpose, allow_backticks=True)
            if not command.strip():
                raise ValueError("commands must not contain empty commands")
        for note in self.notes:
            _require_single_line("note", note, allow_backticks=True)
        if len({path for path, _ in self.layout}) != len(self.layout):
            raise ValueError("layout paths must be unique")
        if len({command for command, _ in self.commands}) != len(self.commands):
            raise ValueError("commands must be unique")


def _require_single_line(
    label: str, value: str, *, allow_backticks: bool = False
) -> None:
    if "\n" in value or "\r" in value or ("`" in value and not allow_backticks):
        detail = "single line"
        if not allow_backticks:
            detail += " without backticks"
        raise ValueError(f"{label} must be {detail}")


def _validate_project_path(path: str) -> None:
    """Require a normalized, relative path that remains inside the project."""
    _require_single_line("layout path", path)
    if not path or path.startswith(("/", "\\")) or "\\" in path:
        raise ValueError(
            f"layout path must be a non-empty relative POSIX path: {path!r}"
        )
    normalized = path[:-1] if path.endswith("/") else path
    parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"layout path is not normalized: {path!r}")


def _escape_markdown(value: str) -> str:
    """Escape inline Markdown punctuation in caller-supplied prose."""
    return re.sub(r"([\\`*_{}\[\]()#+.!|>])", r"\\\1", value)


def _inline_code(value: str) -> str:
    """Render one validated single-line value as inline code."""
    return f"`{value}`"


def _render_agents_md(context: ProjectMetadataContext) -> str:
    features = ", ".join(_inline_code(feature) for feature in context.features)
    if not features:
        features = "none declared by the selected template"

    lines = [
        f"# Agent Guide: {context.project_name}",
        "",
        "This file is project-specific guidance for coding agents. `README.md` is",
        "the human quickstart; this file adds the project map, commands, and the",
        "QuadKit conventions relevant to this scaffold. Update it when the project",
        "layout or workflow changes.",
        "",
        "## Project summary",
        "",
        _escape_markdown(context.summary),
        "",
        f"- Scaffold: {_inline_code(context.template_name)}",
        f"- Python package: {_inline_code(context.package_name)}",
        f"- Framework features: {features}",
        "",
        "## Start here",
        "",
        "1. Read `README.md` for the project overview and quickstart.",
        "2. Read `application.yaml` before changing runtime configuration.",
        f"3. Treat `src/{context.package_name}/app.py` as the composition root; inspect it before changing module wiring.",
        "4. Consult the linked QuadKit docs when a framework convention is unclear.",
        "",
        "## Useful commands",
        "",
    ]
    if context.commands:
        for command, purpose in context.commands:
            lines.append(f"- {_inline_code(command)} — {_escape_markdown(purpose)}")
    else:
        lines.append("- No project commands were supplied by the scaffold context.")

    lines += ["", "## Project map", ""]
    for path, purpose in context.layout:
        lines.append(f"- {_inline_code(path)} — {_escape_markdown(purpose)}")

    lines += [
        "",
        "## QuadKit conventions",
        "",
        "- Preserve the existing project tree: feature code belongs in its feature",
        "  package; cross-cutting code belongs in `shared/`; bounded contexts live",
        "  under `modules/<name>/` when this project uses modules.",
        "- Keep the composition root focused on assembling configuration, providers,",
        "  and modules. Put business behavior in services/domain types rather than",
        "  growing app wiring into a second service locator.",
        "- Prefer the framework's typed protocols and constructor injection. Use",
        "  `Result[T, E]` for expected domain failures and exceptions for unexpected",
        "  infrastructure failures; follow the existing local patterns first.",
        "- Keep I/O asynchronous where the surrounding API is asynchronous. Do not",
        "  introduce a parallel `models/` tree; follow the generated `domains/`",
        "  layout and the canonical QuadKit project-structure guide.",
        "- Add or update tests with behavior changes. Keep configuration examples",
        "  and tests aligned with the actual package set in `pyproject.toml`.",
        "",
        "## QuadKit references",
        "",
        "- [For coding agents](https://oridecon.dev/quadkit/getting-started/for-coding-agents/)",
        "- [Project structure](https://oridecon.dev/quadkit/getting-started/project-structure/)",
        "- [Testing guide](https://oridecon.dev/quadkit/guides/testing/)",
        "- [Common mistakes](https://oridecon.dev/quadkit/getting-started/common-mistakes/)",
    ]

    if context.dependencies:
        lines += ["", "## Declared dependencies", ""]
        lines.extend(f"- {_inline_code(item)}" for item in context.dependencies)

    if context.notes:
        lines += ["", "## Important project notes", ""]
        lines.extend(f"- {_escape_markdown(note)}" for note in context.notes)

    return "\n".join(lines) + "\n"


def render_project_metadata(
    context: ProjectMetadataContext,
) -> Mapping[str, str]:
    """Return deterministic project metadata files for *context*.

    The initial generated-app profile emits only ``AGENTS.md``. It deliberately
    does not create website-only resources such as ``llms.txt``, crawler rules,
    or an Agent Skills pack.
    """
    return {"AGENTS.md": _render_agents_md(context)}
