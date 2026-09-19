"""Shared primitives for filesystem-backed code generators."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quadkit.contracts.cli.generators import (
    CollisionPolicy as CollisionPolicy,
)
from quadkit.contracts.cli.generators import (
    GenerationOptions as GenerationOptions,
)
from quadkit.contracts.cli.generators import (
    GenerationResult as GenerationResult,
)
from quadkit.contracts.cli.generators import (
    find_project_anchor as find_project_anchor,
)
from quadkit.contracts.cli.generators import (
    pascal_case as pascal_case,
)
from quadkit.contracts.cli.generators import (
    resolve_options as resolve_options,
)
from quadkit.contracts.cli.generators import (
    snake_case as snake_case,
)
from quadkit.contracts.cli.generators import (
    validate_component_name as validate_component_name,
)
from quadkit.contracts.exceptions.infra import CollidingFileError, InfrastructureError

if TYPE_CHECKING:
    import jinja2


class GeneratorBase:
    """Base for interactive code scaffolders (name-based, file-producing).

    Rendering requires the optional ``codegen`` extra
    (``uv add 'quadkit[codegen]'``); construction, name normalization,
    and guarded file writes work without it.
    """

    def __init__(
        self,
        output_dir: str | Path = "src",
        template_root: str | Path | None = None,
    ) -> None:
        self.raw_output_dir = Path(output_dir)
        self.output_dir = self._resolve_output_dir(self.raw_output_dir)
        self.template_root = self._resolve_template_root(template_root)
        self._environment: jinja2.Environment | None = None
        self._staged: list[tuple[Path, str]] = []

    def generate(self, name: str, **options: Any) -> GenerationResult:
        raise NotImplementedError

    # ── staged generation ────────────────────────────────────────────

    def stage(self, rel_path: str | Path, content: str) -> None:
        """Queue a rendered file for the next :meth:`commit`.

        Validates immediately (traversal guard, duplicate detection) so a
        misdirected or double-staged file fails before any I/O.

        Args:
            rel_path: Path relative to ``output_dir`` (absolute paths are
                accepted when already inside ``output_dir``).
            content: Full rendered file content.

        Raises:
            ValueError: If the path escapes ``output_dir`` or was already
                staged in this run.
        """
        target = self._ensure_inside_output(rel_path)
        for staged_path, _ in self._staged:
            if staged_path == target:
                raise ValueError(f"Path {target} is already staged")
        self._staged.append((target, content))

    def commit(self, options: GenerationOptions | None = None) -> GenerationResult:
        """Validate and write every staged file atomically (validate-all-then-write-all).

        Collision checks against disk run for **all** staged paths before
        the first byte is written; under
        :attr:`CollisionPolicy.FAIL` any collision raises
        ``CollidingFileError`` leaving the tree untouched. Writes happen
        in sorted path order for deterministic trees.

        Args:
            options: Fully-resolved run options; defaults to SKIP.

        Returns:
            The resulting :class:`GenerationResult`. With ``dry_run`` the
            same result is computed without touching disk.

        Raises:
            CollidingFileError: Under the FAIL policy when a staged path
                already exists.
        """
        resolved = options if options is not None else resolve_options()
        actions: dict[Path, str] = {}
        for target, _content in self._staged:
            if not target.exists():
                actions[target] = "created"
            elif resolved.policy is CollisionPolicy.OVERWRITE:
                actions[target] = "overwritten"
            elif resolved.policy is CollisionPolicy.FAIL:
                raise CollidingFileError(
                    f"Generated file {target} collides with an existing "
                    "file under collision policy FAIL"
                )
            else:
                actions[target] = "skipped"

        created: list[Path] = []
        skipped: list[Path] = []
        overwritten: list[Path] = []
        for target in sorted(actions, key=str):
            action = actions[target]
            if action == "skipped":
                skipped.append(target)
                continue
            content = next(c for p, c in self._staged if p == target)
            if not resolved.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            if action == "overwritten":
                overwritten.append(target)
            else:
                created.append(target)

        self._staged = []
        return GenerationResult(
            files_created=created,
            files_skipped=skipped,
            files_overwritten=overwritten,
        )

    def finalize(self, result: GenerationResult) -> GenerationResult:
        """Post-commit hook for transforms (formatting, verification).

        Subclasses override to post-process committed files; the default
        returns *result* unchanged.
        """
        return result

    @property
    def env(self) -> jinja2.Environment:
        """Public accessor for the Jinja2 environment (lazy-built)."""
        if self._environment is None:
            self._environment = self._build_environment()
        return self._environment

    def _build_environment(self) -> jinja2.Environment:
        try:
            import jinja2
        except ImportError as exc:
            raise InfrastructureError(
                "jinja2 is required for template rendering but is not "
                "installed. Install the codegen extra: "
                "uv add 'quadkit[codegen]' (or pip install 'quadkit[codegen]')"
            ) from exc
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_root),
            autoescape=False,  # noqa: S701 - code generation templates are not HTML
            trim_blocks=False,
            lstrip_blocks=False,
            keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
        )

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

    def write_file(
        self,
        file_path: Path,
        content: str,
        *,
        dry_run: bool = False,
        force: bool = False,
    ) -> GenerationResult:
        existed = file_path.exists()

        self._ensure_inside_output(file_path)

        if existed and not force:
            return GenerationResult(files_skipped=[file_path])

        if not dry_run:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        if existed and force:
            return GenerationResult(files_overwritten=[file_path])

        return GenerationResult(files_created=[file_path])

    def _ensure_inside_output(self, rel_path: str | Path) -> Path:
        """Resolve *rel_path* against ``output_dir`` and enforce the traversal guard.

        Returns:
            The resolved absolute target path.

        Raises:
            ValueError: If the resolved path escapes ``output_dir``.
        """
        target = Path(rel_path)
        if not target.is_absolute():
            target = Path(self.output_dir) / target

        # Path-traversal guard: the resolved target must stay inside the
        # generator's output directory (spec finding 15).
        base = Path(self.output_dir).resolve()
        resolved = target.resolve()
        if not resolved.is_relative_to(base):
            raise ValueError(
                f"Generated path {rel_path} escapes output directory {base}"
            )
        return target

    @classmethod
    def _resolve_output_dir(cls, output_dir: Path) -> Path:
        """Resolve ``output_dir`` to an absolute path before any fs mutation.

        Absolute paths pass through untouched. Relative paths anchor to the
        nearest ancestor with a real project manifest, so generators invoked
        from a subdirectory still write into the right package. Refusal
        happens here — before any ``mkdir`` — so a misdirected run leaves no
        stray directories behind.

        Raises:
            ValueError: If a relative path has no resolvable project anchor.
        """

        if output_dir.is_absolute():
            return output_dir

        anchor = find_project_anchor(Path.cwd())
        if anchor is None:
            raise ValueError(
                f"relative output_dir {output_dir.as_posix()!r} cannot be "
                "resolved: run inside the package that should receive the "
                "generated code, or pass an absolute --output-dir"
            )
        return anchor / output_dir

    def _resolve_template_root(self, template_root: str | Path | None = None) -> Path:
        module_path = Path(inspect.getfile(self.__class__)).resolve().parent
        roots = self._template_search_roots(
            template_root,
            project_anchor=find_project_anchor(Path.cwd()),
            module_name=type(self).__module__,
            package_fallbacks=[
                module_path / "templates",
                module_path.parent / "templates",
            ],
        )
        return next((r for r in roots if r.exists()), roots[-1])

    @staticmethod
    def _template_search_roots(
        template_root: str | Path | None,
        *,
        project_anchor: Path | None = None,
        module_name: str = "",
        package_fallbacks: list[Path] | None = None,
    ) -> list[Path]:
        """Build the ordered candidate roots: explicit > stubs override > package."""
        candidates: list[Path] = []
        if template_root is not None:
            candidates.append(Path(template_root))
        override = GeneratorBase._stub_override_root(module_name, project_anchor)
        if override is not None:
            candidates.append(override)
        if package_fallbacks:
            candidates.extend(package_fallbacks)
        else:
            candidates.extend([Path("templates"), Path("../templates")])
        return candidates

    @staticmethod
    def _stub_override_root(
        module_name: str, project_anchor: Path | None
    ) -> Path | None:
        """Return ``<anchor>/stubs/<dotted-package-as-path>`` for *module_name*.

        Only ``quadkit.*`` modules get an override layer; the package path
        stops before the ``cli`` segment (``quadkit.web.cli.generators.x``
        → ``stubs/quadkit/web``). Returns None when there is no anchor or
        the module lives outside the framework namespace.
        """
        if project_anchor is None:
            return None
        parts = module_name.split(".")
        if not parts or parts[0] != "quadkit":
            return None
        cli_index = parts.index("cli") if "cli" in parts else -1
        pkg_parts = parts[:cli_index] if cli_index >= 2 else parts[:2]
        return Path(project_anchor).joinpath("stubs", *pkg_parts)

    @staticmethod
    def _to_pascal_case(name: str) -> str:
        return pascal_case(name)

    @staticmethod
    def _to_snake_case(name: str) -> str:
        return snake_case(name)

    @classmethod
    def _validate_component_name(cls, name: str) -> str:
        return validate_component_name(name)

    @staticmethod
    def _import_parts(output_dir: str | Path) -> tuple[str, ...] | None:
        """Split an output directory into dotted parts below the import root.

        Generated projects are src-layout: ``src`` is the import root, so a
        directory ``<project>/src/app/controllers`` imports as
        ``app.controllers`` and ``<project>/src/controllers`` as
        ``controllers``.

        Args:
            output_dir: Absolute or relative directory receiving the
                generated file.

        Returns:
            The dotted path parts below the import root, or ``None`` when the
            directory cannot be anchored to a project (tests, scratch dirs),
            leaving callers to fall back to a bare package name.
        """
        path = Path(output_dir).resolve()
        anchor = find_project_anchor(path)
        if anchor is None:
            return None
        try:
            relative = path.relative_to(anchor.resolve())
        except ValueError:
            return None
        parts = [part for part in relative.parts if part not in {"", "."}]
        if "src" in parts:
            parts = parts[parts.index("src") + 1 :]
        return tuple(part for part in parts if part.isidentifier())

    @staticmethod
    def _get_package_name(output_dir: str | Path) -> str:
        """Convert an output directory path to a dotted Python package name.

        The result is relative to the project's import root so generated
        cross-package imports resolve in src-layout projects. When the
        directory cannot be anchored to a project the raw path is returned as
        a dotted string (the historical behaviour).

        Args:
            output_dir: Absolute or relative directory receiving the
                generated file.

        Returns:
            The dotted package name for the directory.
        """
        parts = GeneratorBase._import_parts(output_dir)
        if parts is None:
            return Path(output_dir).as_posix().replace("/", ".")
        return ".".join(parts)

    @staticmethod
    def _sibling_package(output_dir: str | Path, sibling: str) -> str:
        """Return the dotted import path for a sibling component package.

        Component generators write into sibling directories under the same
        root (``src/controllers``, ``src/repositories``, ``src/models``), so a
        controller needs the *repository* sibling's import path — which
        differs by project structure. For example, in the ``structured``
        layout the repository package is ``repositories``, while in the
        ``minimal`` layout it is ``app.repositories``.

        Args:
            output_dir: The directory this generator writes into.
            sibling: Name of the sibling package directory.

        Returns:
            The dotted import path of the sibling package.
        """
        parts = GeneratorBase._import_parts(output_dir)
        if parts is None:
            return sibling
        return ".".join((*parts[:-1], sibling))


class TemplateGeneratorBase:
    """Base for programmatic template renderers (context-based, object-returning)."""

    def generate(self, context: dict[str, object]) -> list[object]:
        raise NotImplementedError
