"""Pytest bootstrap for the WebSocket Echo demo.

WebSocket round trips run through ``WebTestBed`` — the public testing
package's in-process bed, whose client carries WebSocket support the
plain ``httpx`` transport does not.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from websocket_echo.app import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_cwd() -> None:
    os.chdir(ROOT)
