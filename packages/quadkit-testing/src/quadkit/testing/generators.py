"""Golden-tree assertions for code generators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import GenerationResult


def assert_generated_tree(
    generator: Any,
    name: str,
    *,
    root: Path,
    expected_files: dict[str, str],
    **kwargs: object,
) -> GenerationResult:
    """Run *generator* and assert the exact file tree produced under *root*.

    The generator must write every file below *root*. Missing files, extra
    files, and content mismatches all fail with explicit messages.

    Args:
        generator: A constructed generator instance exposing ``generate``.
        name: Name passed through to ``generate``.
        root: Directory the generator is configured to write into.
        expected_files: Mapping of ``root``-relative paths to exact
            expected file content.
        **kwargs: Forwarded to ``generate``.

    Returns:
        The :class:`GenerationResult` from ``generate``, for further
        caller-side assertions.

    Raises:
        AssertionError: On any missing/extra/mismatched file.
    """
    result: GenerationResult = generator.generate(name, **kwargs)

    actual_files = {
        str(p.relative_to(root)): p for p in sorted(root.rglob("*")) if p.is_file()
    }

    missing = sorted(set(expected_files) - set(actual_files))
    extra = sorted(set(actual_files) - set(expected_files))
    assert not missing, f"Generated tree is missing files: {missing}"
    assert not extra, f"Generated tree has unexpected files: {extra}"

    mismatched = [
        rel
        for rel, expected in expected_files.items()
        if actual_files[rel].read_text(encoding="utf-8") != expected
    ]
    assert not mismatched, f"Content mismatch in generated files: {mismatched}"

    return result
