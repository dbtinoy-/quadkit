"""Run the documented local in-memory inbox examples against the real service."""

from __future__ import annotations

from pathlib import Path
import textwrap

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "heading"),
    [
        ("GUIDE.md", "## Inbox (In-App Notifications)"),
        ("CHANNELS.md", "## Inbox Service"),
    ],
)
async def test_inbox_example_runs(filename: str, heading: str) -> None:
    docs = Path(__file__).resolve().parents[2] / "docs"
    text = (docs / filename).read_text(encoding="utf-8")
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    code = section.split("```python\n", 1)[1].split("```", 1)[0]
    namespace: dict[str, object] = {}
    exec("async def example():\n" + textwrap.indent(code, "    "), namespace)  # noqa: S102
    await namespace["example"]()  # type: ignore[operator]
