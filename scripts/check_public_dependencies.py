#!/usr/bin/env python3
"""Check that a generated repository has only published package dependencies.

The release exporter performs the authoritative full-text scan against the
private source tree. This small copy is shipped with the public repository so
public CI can guard dependency metadata and install commands without carrying
a private-package catalogue.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
import tomllib

#: Names this copy of the gate is allowed to see. It must stay equal to
#: ``export_public.PUBLIC_PACKAGES``' project names — a set that only ever
#: grows — so ``tests/dev/test_export_public.py`` pins the two together. The
#: literal has to stay a literal: this file ships to the public repository,
#: which has no access to the monorepo's catalogue.
PUBLISHED_DISTRIBUTIONS = frozenset(
    {
        "quadkit",
        "quadkit-contracts",
        "quadkit-web",
        "quadkit-testing",
        "quadkit-cli",
        "quadkit-sql",
        "quadkit-auth",
        "quadkit-cache",
        "quadkit-storage",
        "quadkit-events",
        "quadkit-tasks",
        "quadkit-http",
        "quadkit-monitor",
    }
)
DISTRIBUTION_NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
INSTALL_COMMAND = re.compile(
    r"\b(?:pip|uv)\s+(?:install|add|remove)\s+([A-Za-z0-9][A-Za-z0-9._-]*)"
)


def _quadkit_name(value: object) -> str | None:
    """Extract a distribution name from a requirement or source key."""

    if not isinstance(value, str):
        return None
    match = DISTRIBUTION_NAME.match(value)
    if match and match.group(1).lower().startswith("quadkit"):
        return match.group(1).lower().replace("_", "-")
    return None


def _metadata_references(manifest: Path) -> set[str]:
    """Collect Quadkit names from dependency-bearing TOML fields."""

    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    project = data.get("project", {})
    references: set[str] = set()
    for requirement in project.get("dependencies", []):
        if name := _quadkit_name(requirement):
            references.add(name)
    for requirements in project.get("optional-dependencies", {}).values():
        for requirement in requirements:
            if name := _quadkit_name(requirement):
                references.add(name)
    for group in data.get("dependency-groups", {}).values():
        if isinstance(group, list):
            for requirement in group:
                if name := _quadkit_name(requirement):
                    references.add(name)
    for name in data.get("tool", {}).get("uv", {}).get("sources", {}):
        if normalized := _quadkit_name(name):
            references.add(normalized)
    return references


def main() -> int:
    """Return non-zero if dependency metadata names an unpublished distribution."""

    root = Path.cwd()
    references: list[str] = []
    for manifest in sorted(root.rglob("pyproject.toml")):
        try:
            names = _metadata_references(manifest)
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            print(f"invalid manifest {manifest}: {exc}", file=sys.stderr)
            return 1
        references.extend(
            f"{manifest.relative_to(root)}: {name}"
            for name in sorted(names - PUBLISHED_DISTRIBUTIONS)
        )

    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in INSTALL_COMMAND.finditer(text):
            if (
                name := _quadkit_name(match.group(1))
            ) and name not in PUBLISHED_DISTRIBUTIONS:
                references.append(f"{path.relative_to(root)}: {name}")

    if references:
        print("unpublished distribution dependencies found:", file=sys.stderr)
        print("\n".join(references), file=sys.stderr)
        return 1
    print("public dependency surface: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
