"""Pytest bootstrap for the demo hub.

Two jobs:

1. Make imports and config discovery work regardless of *where* pytest is
   invoked: chdir into this demo's root (where ``application.yaml`` lives)
   and put ``src`` on ``sys.path``. The framework auto-discovers
   ``application.yaml`` from the working directory, so after this chdir no
   custom configuration loader is needed anywhere.
2. Re-pin cwd before every test so parallel or fixture-driven cwd changes
   never break yaml discovery.

    uv run pytest examples/example-hub/tests -q        # from repo root works too
"""

from __future__ import annotations

from pathlib import Path
import os
import sys

import pytest

_DEMO_ROOT = Path(__file__).resolve().parent.parent

# Quadkit discovers application.yaml from cwd — pin it so tests work
# from any invocation point (repo root or in-demo).
os.chdir(_DEMO_ROOT)
# Add src/ to sys.path so ``from example_hub...`` resolves in tests.
sys.path.insert(0, str(_DEMO_ROOT / "src"))


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    """Pin cwd to the demo root before every test.

    Module-level os.chdir() runs once at import time.  If any test or
    fixture changes cwd (e.g. tmp_path, other demos in parallel), this
    fixture re-pins it before every test function.
    """
    os.chdir(_DEMO_ROOT)
