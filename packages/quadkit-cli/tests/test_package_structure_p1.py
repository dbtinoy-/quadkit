"""Structural compliance tests for the package layout."""
from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src/quadkit/cli"


def test_package_uses_lib_not_utils() -> None:
    assert (SRC_ROOT / "lib").exists()
    assert not (SRC_ROOT / "utils").exists()
