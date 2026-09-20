"""Shared configuration for the quadkit-testing unit suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure _integration_helpers.py in this directory is importable regardless of
# pytest rootdir: the repository runs with --import-mode=importlib, which does
# not put a test directory on sys.path, so a workspace-wide run (the root
# testpaths, which `make ci` and the coverage job use) needs this bootstrap.
sys.path.insert(0, str(Path(__file__).parent))
