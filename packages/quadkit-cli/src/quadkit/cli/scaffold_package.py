"""Canonical quadkit-* extension package scaffold.

``quadkit new package my-feature`` renders this layout with the real
framework APIs:

- ``pyproject.toml`` — hatchling build, pytest-asyncio config
- ``src/quadkit/<package>/`` — package source with ``py.typed``
- ``di/provider.py`` — ``Provider`` subclass using the real
  ``quadkit.di.provider`` base and ``quadkit.di`` container protocols
- ``tests/unit/test_provider.py`` — lifecycle smoke tests
"""

from __future__ import annotations

from pathlib import Path


def _provider_module(package_name: str, class_name: str) -> str:
    return f'''"""{class_name} provider for the Quadkit DI container."""
from __future__ import annotations

from quadkit.contracts.core.di import BootContainerProtocol
from quadkit.di import ContainerRegistrarProtocol, Provider, ProviderPriority


class {class_name}Provider(Provider):
    """Registers {package_name} services into the application container.

    Add this provider to your application via ``application.add_provider()``.
    """

    name = "{package_name}"
    # priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register {package_name} services.

        Args:
            container: The DI container registrar.
        """
        # Example:
        # container.singleton({package_name}.service.MyService)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Boot {package_name} services after all providers are registered.

        Args:
            container: The read-only container resolver.
        """

    async def shutdown(self) -> None:
        """Tear down {package_name} services on application shutdown."""


__all__ = ["{class_name}Provider"]
'''


def _init_module(package_name: str, class_name: str, description: str) -> str:
    return f'''"""quadkit-{package_name} — {description}."""
from __future__ import annotations

from quadkit.{package_name}.di.provider import {class_name}Provider

__all__ = ["{class_name}Provider"]
'''


def _test_module(package_name: str, class_name: str) -> str:
    return f'''"""Unit tests for {class_name}Provider."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.{package_name}.di.provider import {class_name}Provider


class Test{class_name}Provider:
    """Tests for the {class_name}Provider."""

    async def test_provider_has_expected_name(self) -> None:
        """Provider name is the package slug."""
        provider = {class_name}Provider()
        assert provider.name == "{package_name}"

    async def test_register_does_not_raise(self) -> None:
        """register() completes on a mock registrar."""
        container = AsyncMock()
        provider = {class_name}Provider()
        await provider.register(container)

    async def test_shutdown_does_not_raise(self) -> None:
        """shutdown() completes without errors."""
        provider = {class_name}Provider()
        await provider.shutdown()
'''


def _pyproject(package_name: str, description: str, class_name: str) -> str:
    distribution = "quadkit-" + package_name.replace("_", "-")
    return f"""[project]
name = "{distribution}"
version = "0.1.0"
description = "{description}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "quadkit",
    "quadkit-contracts",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.6.0",
    "mypy>=1.10.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/quadkit/{package_name}"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
"""


def _readme(package_name: str, class_name: str, description: str) -> str:
    distribution = "quadkit-" + package_name.replace("_", "-")
    return f"""# {distribution}

{description}

## Usage

```python
from quadkit.{package_name} import {class_name}Provider

# In your composition root:
# application.add_providers([{class_name}Provider()])
```

## Development

```bash
pip install -e .[dev]
pytest
```
"""


def _gitignore() -> str:
    return """# Python
__pycache__/
*.py[cod]
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
"""


def _files(package_name: str, class_name: str, description: str) -> dict[str, str]:
    return {
        "README.md": _readme(package_name, class_name, description),
        "pyproject.toml": _pyproject(package_name, description, class_name),
        ".gitignore": _gitignore(),
        f"src/quadkit/{package_name}/__init__.py": _init_module(
            package_name, class_name, description
        ),
        f"src/quadkit/{package_name}/py.typed": "",
        f"src/quadkit/{package_name}/di/__init__.py": '"""DI providers."""\n',
        f"src/quadkit/{package_name}/di/provider.py": _provider_module(
            package_name, class_name
        ),
        "tests/__init__.py": "",
        "tests/unit/__init__.py": "",
        "tests/unit/test_provider.py": _test_module(package_name, class_name),
    }


def render_package(
    package_name: str,
    target_dir: Path,
    *,
    class_name: str | None = None,
    description: str = "",
) -> list[Path]:
    """Render a canonical quadkit-* extension package into *target_dir*.

    Args:
        package_name: Normalized package slug (underscores, no ``quadkit-``).
        target_dir: Destination directory (must be empty).
        class_name: PascalCase provider name (derived from *package_name*).
        description: Package description for metadata.

    Returns:
        The list of created file paths.
    """
    if target_dir.exists() and any(target_dir.iterdir()):
        raise ValueError(f"Directory {target_dir} is not empty")
    class_name = class_name or "".join(
        part.capitalize() for part in package_name.split("_")
    )
    description = description or f"Quadkit extension package: quadkit-{package_name}"

    created: list[Path] = []
    for relative, content in _files(package_name, class_name, description).items():
        path = target_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(path)
    return created


__all__ = ["render_package"]
