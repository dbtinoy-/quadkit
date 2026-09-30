"""Code generator contracts for Quadkit CLI extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
from pathlib import Path
import re
import tomllib
from typing import Any, Protocol, runtime_checkable


def _json_dumps(data: dict[str, Any], sort_keys: bool = False) -> bytes:
    """Serialize dict to JSON bytes using the stdlib json module."""
    return json.dumps(data, sort_keys=sort_keys).encode("utf-8")


@dataclass(slots=True, frozen=True)
class GenerationResult:
    """Result of a generation operation."""

    files_created: list[Path] = field(default_factory=list)
    files_skipped: list[Path] = field(default_factory=list)
    files_overwritten: list[Path] = field(default_factory=list)

    def to_manifest(self) -> dict[str, str]:
        """Map each touched path to its action.

        Returns:
            A ``{path: action}`` dict where action is ``"created"``,
            ``"skipped"``, or ``"overwritten"``. Pure data — no I/O.
        """
        manifest: dict[str, str] = {}
        for path in self.files_created:
            manifest[str(path)] = "created"
        for path in self.files_skipped:
            manifest[str(path)] = "skipped"
        for path in self.files_overwritten:
            manifest[str(path)] = "overwritten"
        return manifest


class CollisionPolicy(StrEnum):
    """What to do when a generated file already exists on disk."""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    """Standardized options for code-generation runs.

    Attributes:
        dry_run: Compute the would-be result without touching disk.
        force: Convenience alias; resolves to ``OVERWRITE`` unless an
            explicit ``policy`` is given.
        quiet: Suppress non-essential output.
        policy: Explicit collision policy; wins over ``force`` when set.
    """

    dry_run: bool = False
    force: bool = False
    quiet: bool = False
    policy: CollisionPolicy | None = None

    def __post_init__(self) -> None:
        """Normalize ``policy`` so it is never None after construction.

        Explicit policy wins; otherwise ``force`` maps to OVERWRITE;
        otherwise SKIP.
        """
        if self.policy is None:
            object.__setattr__(
                self,
                "policy",
                CollisionPolicy.OVERWRITE if self.force else CollisionPolicy.SKIP,
            )


def resolve_options(
    *,
    dry_run: bool = False,
    force: bool = False,
    quiet: bool = False,
    policy: CollisionPolicy | None = None,
) -> GenerationOptions:
    """Normalize legacy kwargs into a fully-resolved :class:`GenerationOptions`.

    Resolution order: an explicit ``policy`` always wins; otherwise
    ``force=True`` maps to :attr:`CollisionPolicy.OVERWRITE`; otherwise
    the default SKIP applies. ``dry_run`` and ``quiet`` are orthogonal.

    Args:
        dry_run: Preview mode; never writes to disk.
        force: Legacy overwrite flag.
        quiet: Suppress non-essential output.
        policy: Explicit collision policy.

    Returns:
        Options with ``policy`` guaranteed non-None.
    """
    resolved_policy = (
        policy
        if policy is not None
        else (CollisionPolicy.OVERWRITE if force else CollisionPolicy.SKIP)
    )
    return GenerationOptions(
        dry_run=dry_run,
        force=force,
        quiet=quiet,
        policy=resolved_policy,
    )


@runtime_checkable
class GeneratorProtocol(Protocol):
    """Protocol for code generators used by CLI extensions."""

    name: str
    description: str

    def generate(self, name: str, **kwargs: Any) -> GenerationResult:
        """Generate files for the given name.

        Args:
            name: The name to generate code for (e.g. module name, provider name).
            **kwargs: Additional generation parameters.

        Returns:
            A ``GenerationResult`` describing which files were created/skipped.
        """
        ...


_VALID_COMPONENT_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def snake_case(name: str) -> str:
    """Convert any identifier spelling to ``snake_case``.

    Handles spaces, hyphens, and CamelCase boundaries; leading/trailing
    separators are stripped.

    Args:
        name: Raw identifier as provided by the user.

    Returns:
        The normalized ``snake_case`` form.

    Example:
        ```python
        snake_case("UserProfile-ID")  # -> "user_profile_id"
        ```
    """

    compact = re.sub(r"[\s-]+", "_", name)
    separated = re.sub(r"([A-Z])", r"_\1", compact)
    return separated.lower().strip("_")


def pascal_case(name: str) -> str:
    """Convert any identifier spelling to ``PascalCase``.

    Normalizes through :func:`snake_case` first, so mixed inputs behave
    consistently.

    Args:
        name: Raw identifier as provided by the user.

    Returns:
        The normalized ``PascalCase`` form.

    Example:
        ```python
        pascal_case("user_profile")  # -> "UserProfile"
        ```
    """

    return "".join(part.capitalize() for part in snake_case(name).split("_") if part)


def validate_component_name(name: str) -> str:
    """Validate a user-supplied component name for safe code generation.

    Rejects path separators, dot segments, and names that do not start
    with an alphanumeric character, so a name can never escape the
    generator output directory or poison emitted identifiers.

    Args:
        name: Raw component name.

    Returns:
        The validated name unchanged on success.

    Raises:
        ValueError: If the name contains path separators, dot segments,
            or starts with a non-alphanumeric character.
    """

    if not _VALID_COMPONENT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid generator name {name!r}: must match "
            f"{_VALID_COMPONENT_NAME_RE.pattern!r}"
        )
    return name


def find_project_anchor(start: Path) -> Path | None:
    """Return the nearest ancestor directory with a real ``[project]`` table.

    Virtual workspace roots (``[tool.uv.workspace]`` only, no
    ``[project]``) are deliberately skipped: generated application code
    must never land in the framework monorepo.

    Args:
        start: Directory to walk upward from.

    Returns:
        The nearest ancestor containing a ``pyproject.toml`` with a
        ``[project]`` table, or ``None`` when no anchor exists.
    """

    for candidate in (start, *start.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            manifest = pyproject.read_text(encoding="utf-8", errors="ignore")
            parsed = tomllib.loads(manifest)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        if "project" in parsed:
            return candidate
    return None


__all__ = [
    "CollisionPolicy",
    "GenerationOptions",
    "GenerationResult",
    "GeneratorProtocol",
    "find_project_anchor",
    "pascal_case",
    "resolve_options",
    "snake_case",
    "validate_component_name",
]
