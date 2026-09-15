"""GuardProtocol to prevent importing Alembic/SQLAlchemy in core package.

This test fails if any source file under `quadkit/src/quadkit` contains a
literal import of `alembic` or `sqlalchemy`. Tests and docs are excluded; this
is intended to prevent accidental reintroduction of import-time dependencies
on DB packages in the core package.
"""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2] / "src" / "quadkit"
PATTERNS = [
    r"\bimport\s+alembic\b",
    r"\bfrom\s+alembic\b",
    r"\bimport\s+sqlalchemy\b",
    r"\bfrom\s+sqlalchemy\b",
]


def test_no_alembic_sqlalchemy_imports():
    matches = []
    for path in ROOT.rglob("*.py"):
        # Skip tests and generated docs/helpers
        if "tests" in path.parts or "docs" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for pat in PATTERNS:
            for m in re.finditer(pat, text):
                # Compute the line number from the character offset
                line_num = text[: m.start(0)].count("\n")
                line = text.splitlines()[line_num].strip()
                # Skip lines where the pattern is inside a string literal
                # (e.g. code-generation helpers that emit "from sqlalchemy ..." strings)
                if line.startswith(("f'", 'f"', "'", '"')):
                    continue
                matches.append(
                    (str(path.relative_to(ROOT.parent.parent)), line_num + 1, line),
                )

    if matches:
        msgs = [f"{match[0]}:{match[1]}:{match[2]}" for match in matches]
        raise AssertionError("Found forbidden DB imports in core:\n" + "\n".join(msgs))
