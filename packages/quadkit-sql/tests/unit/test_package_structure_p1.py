"""Structural compliance tests for quadkit-sql."""

from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PACKAGE_ROOT / "src/quadkit/sql"


def test_sql_uses_canonical_repo_and_query_layout() -> None:
    assert (SRC_ROOT / "repositories").exists()
    assert not (SRC_ROOT / "repository").exists()
    assert (SRC_ROOT / "query").exists()
    assert not (SRC_ROOT / "query_builder").exists()


def test_sql_uses_backends_and_lib() -> None:
    assert (SRC_ROOT / "backends").exists()
    assert not (SRC_ROOT / "drivers").exists()
    assert (SRC_ROOT / "lib").exists()
    assert not (SRC_ROOT / "utils").exists()
