"""Import-boundary tests proving contracts load with zero extension side effects."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CONTRACTS_ROOT = Path(__file__).resolve().parents[4]
SRC = CONTRACTS_ROOT / "quadkit-contracts" / "src"

FORBIDDEN_MODULES = (
    "quadkit.ai.llm",
    "quadkit.ai.relay",
    "quadkit.web",
    "quadkit.http",
)


def test_relay_import_has_no_extension_side_effects() -> None:
    """Importing the relay package must not load AI extension modules."""
    script = (
        "import sys; "
        "sys.path.insert(0, {src!r}); "
        "import quadkit.contracts.ai.relay; "
        "loaded = sorted(m for m in sys.modules if m == 'quadkit.ai.relay' or m.startswith('quadkit.ai.llm.') or m.startswith('quadkit.ai.relay.')); "
        "assert not loaded, loaded"
    ).format(src=str(SRC))
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(CONTRACTS_ROOT),
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module", FORBIDDEN_MODULES)
def test_forbidden_modules_not_loaded_by_contracts(module: str) -> None:
    """Contracts never import forbidden extension modules."""
    script = (
        "import sys; "
        "sys.path.insert(0, {src!r}); "
        "import quadkit.contracts.ai.relay; "
        "assert {module!r} not in sys.modules, \"loaded {module!r}\""
    ).format(src=str(SRC), module=module)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(CONTRACTS_ROOT),
    )
    assert result.returncode == 0, result.stderr