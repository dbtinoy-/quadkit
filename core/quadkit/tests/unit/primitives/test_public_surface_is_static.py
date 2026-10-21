"""``quadkit.primitives.__all__`` is a literal, and it matches the lazy map.

A list built from ``_LAZY_IMPORTS`` at runtime exports nothing to a type
checker: under ``implicit_reexport = False`` every ``from quadkit.primitives
import Context`` in an application was an ``attr-defined`` error, while the
import worked at runtime. Keeping the two in step is this test's job.
"""

from __future__ import annotations

import ast
from pathlib import Path

import quadkit.primitives as primitives


def test_all_is_a_literal_list_equal_to_the_lazy_map() -> None:
    source = Path(primitives.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literal: list[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            assert isinstance(node.value, ast.List), "__all__ must be a literal list, not an expression"
            literal = [ast.literal_eval(elt) for elt in node.value.elts]
    assert literal is not None
    assert sorted(literal) == sorted(primitives._LAZY_IMPORTS), "a lazy export is missing from __all__ (or vice versa)"


def test_every_public_name_resolves() -> None:
    for name in primitives.__all__:
        assert getattr(primitives, name) is not None
