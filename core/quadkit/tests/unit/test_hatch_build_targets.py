import os
from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
PACKAGES_DIR = REPO_ROOT / "packages"


def test_hatch_packages_have_wheel_target():
    """Ensure any package that uses hatchling declares a wheel build target."""
    errors = []

    # Packages are at repo root, starting with quadkit-
    for pkg in os.listdir(REPO_ROOT):
        pkg_dir = REPO_ROOT / pkg
        if not pkg.startswith("quadkit-") or not pkg_dir.is_dir():
            continue

        pyproject = pkg_dir / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
        except (ValueError, UnicodeDecodeError, OSError):
            continue

        build_system = data.get("build-system", {})
        requires = build_system.get("requires", [])
        if any(r.startswith("hatchling") for r in requires):
            # must declare wheel target
            hatch = data.get("tool", {}).get("hatch", {})
            targets = hatch.get("build", {}).get("targets", {})
            wheel = targets.get("wheel")
            if not wheel or "packages" not in wheel:
                errors.append(
                    f"Package {pkg} uses hatchling but missing wheel target/packages",
                )

    assert not errors, "\n".join(errors)
