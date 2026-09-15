"""Path shims for the di/module integration tests.

pytest's --import-mode=importlib does not put test directories on
sys.path, so sibling support modules must be fronted here.
"""

import sys
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

# Surface shared fixtures (graph, modules) to pytest.
from _fixtures import *  # noqa: F401,F403 — fixture re-export
from _fixtures import graph  # noqa: F401 — explicit for readers
