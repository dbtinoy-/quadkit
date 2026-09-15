"""Test that no print() statements exist in production code.

Enforces Ruff T201 rule: no print() statements in production code.
All logging must use structured logging via quadkit.logging.get_logger().
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


def test_no_print_statements_in_core() -> None:
    """Verify that no print() calls exist in core quadkit source files."""
    issues: list[str] = []
    src_dir = Path(__file__).parent.parent.parent / "src" / "quadkit"

    for root, dirs, files in os.walk(src_dir):
        # Skip test directories
        dirs[:] = [d for d in dirs if d not in ("test", "tests", "__pycache__")]

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = Path(root) / file
            rel_path = file_path.relative_to(src_dir.parent)

            try:
                with open(file_path) as f:
                    content = f.read()
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "print":
                        issues.append(f"{rel_path}:{node.lineno}")

    assert len(issues) == 0, f"Found {len(issues)} print() calls:\n" + "\n".join(issues)
