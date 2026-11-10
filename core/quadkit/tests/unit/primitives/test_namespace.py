"""Late-installed ``quadkit.*`` trees, and the refresh that makes them visible."""

from __future__ import annotations

import importlib
import sys

import pytest

import quadkit


@pytest.fixture
def probe_tree(tmp_path, monkeypatch):
    """A ``quadkit`` portion that lands on ``sys.path`` after import."""
    tree = tmp_path / "late"
    (tree / "quadkit").mkdir(parents=True)
    (tree / "quadkit" / "late_probe.py").write_text("VALUE = 1\n", encoding="utf-8")
    saved = list(quadkit.__path__)
    monkeypatch.syspath_prepend(str(tree))
    monkeypatch.setattr(quadkit, "__path__", saved)
    try:
        yield tree
    finally:
        quadkit.__path__[:] = saved
        sys.modules.pop("quadkit.late_probe", None)


def test_a_late_tree_is_invisible_until_refreshed(probe_tree):
    """Importing first is not enough: the path was scanned before the tree existed."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("quadkit.late_probe")

    quadkit.refresh_namespace()

    assert str(probe_tree / "quadkit") in quadkit.__path__
    assert importlib.import_module("quadkit.late_probe").VALUE == 1


def test_refresh_drops_a_portion_whose_path_entry_is_gone(probe_tree, monkeypatch):
    """A removed tree must not keep shadowing a fresh install of the same module."""
    quadkit.refresh_namespace()
    assert str(probe_tree / "quadkit") in quadkit.__path__

    monkeypatch.setattr(sys, "path", [item for item in sys.path if item != str(probe_tree)])
    quadkit.refresh_namespace()

    assert str(probe_tree / "quadkit") not in quadkit.__path__
