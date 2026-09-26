"""Shared test configuration and fixtures."""

from pathlib import Path
import sys

# Direct sibling-helper imports (e.g. ``_make_raw_response`` living in a
# sibling test module) resolve through this fronted path because pytest's
# importlib mode does not put test directories on sys.path and this tests
# tree has no ``__init__.py``.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent / "unit"
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))
