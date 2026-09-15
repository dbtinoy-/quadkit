"""Structural compliance tests for the package layout."""
from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src/quadkit/contracts"


def test_package_uses_lib_time_not_internal_time() -> None:
    assert (SRC_ROOT / "lib/time.py").exists()
    assert not (SRC_ROOT / "_internal/time.py").exists()
