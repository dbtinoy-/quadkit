"""Structural compliance tests for quadkit-events."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PACKAGE_ROOT / "src/quadkit/events"


def test_events_uses_types_file_not_directory() -> None:
    assert (SRC_ROOT / "types.py").exists()
    assert not (SRC_ROOT / "types").exists()
    assert not (SRC_ROOT / "enums.py").exists()  # enums merged into types.py


def test_events_subproviders_live_under_di_sub_providers() -> None:
    assert (SRC_ROOT / "di/sub_providers").exists()
    assert (SRC_ROOT / "di/sub_providers/bus_provider.py").exists()
    assert (SRC_ROOT / "di/sub_providers/handler_provider.py").exists()
    assert (SRC_ROOT / "di/sub_providers/manager_provider.py").exists()
    assert (SRC_ROOT / "di/sub_providers/store_provider.py").exists()
    assert not (SRC_ROOT / "buses/sub_provider.py").exists()
    assert not (SRC_ROOT / "handlers/sub_provider.py").exists()
    assert not (SRC_ROOT / "projections/sub_provider.py").exists()
    assert not (SRC_ROOT / "stores/sub_provider.py").exists()
