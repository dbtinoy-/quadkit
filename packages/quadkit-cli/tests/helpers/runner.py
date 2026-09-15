"""Test runner utilities for running all package tests from the workspace.

This module contains a small, reusable test runner originally implemented
as a top-level script. Moving it into `quadkit.testing` makes it
importable and available as a console script entry point.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def _packages_root() -> Path:
    """Return the workspace root (parent of the `packages` directory).

    We locate this file under `packages/quadkit/src/quadkit/testing/run_tests.py`;
    ascend to find the repository packages directory and return its parent.
    """
    p = Path(__file__).resolve()
    # Expected layout: .../packages/quadkit/src/quadkit/testing/run_tests.py
    # parents[4] is the packages directory
    packages_dir = p.parents[4]
    if packages_dir.name != "packages":
        # Fallback: search upwards for a 'packages' directory
        for parent in p.parents:
            candidate = parent / "packages"
            if candidate.exists() and candidate.is_dir():
                packages_dir = candidate
                break
    return packages_dir.parent


def run_package_tests(package_name: str, packages_root: Path | None = None) -> bool:
    """Run tests for a specific package located in the repository packages folder.

    Returns True on success, False on failure.
    """
    packages_root = packages_root or _packages_root()
    package_path = packages_root / "packages" / package_name
    if not package_path.exists():
        return False

    test_dirs = []
    if (package_path / "tests" / "unit").exists():
        test_dirs.append("tests/unit")
    if (package_path / "tests").exists() and not test_dirs:
        test_dirs.append("tests")

    if not test_dirs:
        return True

    success = True
    for test_dir in test_dirs:
        try:
            # Ensure the package's src directory is on PYTHONPATH so pytest
            # can import the package when using the 'src' layout. Also ensure the
            # core 'quadkit' package src is available for packages that import it.
            env = None
            try:
                env = os.environ.copy()
                parts = []
                pkg_src = package_path / "src"
                if pkg_src.exists():
                    parts.append(str(pkg_src))
                core_src = packages_root / "packages" / "quadkit" / "src"
                if core_src.exists():
                    parts.append(str(core_src))

                if parts:
                    existing = env.get("PYTHONPATH", "")
                    new_pp = os.pathsep.join(
                        parts + ([existing] if existing else []),
                    )
                    env["PYTHONPATH"] = new_pp
            except OSError:
                # Fall back to default environment if anything goes wrong
                env = None

            # Validate test_dir to avoid running arbitrary commands
            if test_dir not in ("tests/unit", "tests"):
                raise ValueError("invalid test_dir")

            # test_dir is validated above to prevent arbitrary command execution
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_dir, "--tb=short", "-q"],
                check=False,
                cwd=package_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                success = False

        except subprocess.TimeoutExpired:
            success = False
        except (OSError, subprocess.SubprocessError):
            success = False

    return success


def main(_argv: Iterable[str] | None = None) -> int:
    """Entry point: run the test suites for a predefined set of packages.

    Accepts an optional iterable of strings to allow programmatic use or
    integration with other tooling. Returns an exit code (0 success, 1 fail).
    """
    packages = [
        "quadkit",
        "quadkit-contracts",
        "quadkit-web",
        "quadkit-events",
        "quadkit-sql",
        "quadkit-auth",
        "quadkit-cache",
        "quadkit-queue",
        "quadkit-notification",
        "quadkit-tasks",
        "quadkit-search",
        "quadkit-storage",
        "quadkit-graphql",
        "quadkit-monitor",
        "quadkit-ai",
        "quadkit-cloud",
        "quadkit-connect",
    ]

    results = {}

    packages_root = _packages_root()

    for package in packages:
        results[package] = run_package_tests(package, packages_root)

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    if passed == total:
        return 0
    return 1


__all__ = ["main", "run_package_tests"]
