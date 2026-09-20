"""Round 40 hardening pins — quadkit-cli: bad layout file degrades.

read_project_layout — a pyproject.toml whose bytes are not valid
UTF-8 (UnicodeDecodeError, not in the old OSError/TOMLDecodeError
tuple) falls back to the default ProjectLayout, never a raw raise.

Run with: pytest tests/unit/test_round40_hardening.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.cli.layout import ProjectLayout, read_project_layout

pytestmark = pytest.mark.unit


class TestReadProjectLayout:
    def test_invalid_utf8_falls_back_to_default(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe\x00[tool\n")

        layout = read_project_layout(tmp_path)

        assert isinstance(layout, ProjectLayout)
        assert layout.declared is False
