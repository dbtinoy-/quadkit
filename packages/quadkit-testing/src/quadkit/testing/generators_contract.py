"""Contract harness proving contributed generators actually render."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any


def assert_contributor_generators_render(
    contributor: Any,
    *,
    tmp_path: Path,
    sample_name: str = "demo",
    skip: frozenset[str] = frozenset(),
) -> int:
    """Instantiate and run every generator a contributor declares.

    For each ``GeneratorDefinition`` returned by ``contributor.get_generators()``
    the generator class at ``generator_path`` is instantiated with an absolute
    ``output_dir`` under *tmp_path* (falling back to the default constructor for
    generators that do not accept one) and ``generate(sample_name,
    output_dir=<tmp subdir>)`` is invoked. The process working directory is
    pinned to the per-generator subdirectory for the duration of the run so
    generators that resolve relative paths against ``Path.cwd()`` stay isolated
    from the real project tree.

    Asserts at least one created/overwritten/staged file per generator unless
    its name is in *skip*. A contributor that declares no generators yields a
    return value of 0 — callers assert their own expected minimum via the
    returned count.

    Args:
        contributor: Constructed CLI contributor exposing ``get_generators()``.
        tmp_path: Pytest temporary directory rooting all generated output.
        sample_name: Component name passed to every generator.
        skip: Generator names to exclude (e.g. environment-bound generators).

    Returns:
        The number of generators exercised (declared minus skipped).

    Raises:
        AssertionError: If an exercised generator produces no output.
    """
    exercised = 0
    definitions = contributor.get_generators()
    for definition in definitions:
        if definition.name in skip:
            continue
        module_path, _, cls_name = definition.generator_path.partition(":")
        module = importlib.import_module(module_path)
        generator_cls = getattr(module, cls_name)

        out = tmp_path / definition.contributor / definition.name
        out.mkdir(parents=True, exist_ok=True)
        previous_cwd = Path.cwd()
        os.chdir(out)
        try:
            try:
                generator = generator_cls(output_dir=str(out))
            except TypeError:
                generator = generator_cls()
            result = generator.generate(sample_name, output_dir=str(out))
        finally:
            os.chdir(previous_cwd)

        created = list(getattr(result, "files_created", None) or [])
        overwritten = list(getattr(result, "files_overwritten", None) or [])
        staged_raw = getattr(result, "staged", None) or []
        staged = [
            entry[0] if isinstance(entry, tuple) else getattr(entry, "dest", entry)
            for entry in staged_raw
        ]
        assert created or overwritten or staged, (
            f"generator {definition.name!r} produced no output "
            f"(created={len(created)}, overwritten={len(overwritten)}, "
            f"staged={len(staged)})"
        )
        exercised += 1
    return exercised


__all__ = ["assert_contributor_generators_render"]
