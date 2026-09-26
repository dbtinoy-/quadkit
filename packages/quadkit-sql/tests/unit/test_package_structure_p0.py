"""Structural compliance tests for the P0 package layout rules."""

from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


def test_fixture_artifacts_are_canonicalized() -> None:
    """Keep the checked-in fixture and Alembic config in canonical locations."""
    package_root = Path(__file__).resolve().parents[2]

    assert (package_root / "tests" / "fixtures" / "test.db").exists()
    assert not (package_root / "src" / "quadkit" / "sql" / "test.db").exists()
    assert not (package_root / "test.db").exists()
    assert not (package_root / "tests" / "test.db").exists()
    assert (package_root / "alembic.ini").exists()
    assert not (package_root / "src" / "quadkit" / "sql" / "alembic.ini").exists()


def test_package_root_alembic_ini_uses_stable_script_location() -> None:
    """Ensure the canonical Alembic config does not bake in temp paths."""
    package_root = Path(__file__).resolve().parents[2]
    config = ConfigParser()
    config.read(package_root / "alembic.ini")

    assert config.get("alembic", "script_location", raw=True) == "%(here)s/migrations"
