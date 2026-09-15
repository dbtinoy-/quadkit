"""Config file discovery and loading for CLI commands.

Resolution order:
1. Explicit --config flag
2. QK_CONFIG environment variable
3. Walk up from CWD looking for application.yaml / application.yml
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, cast

import aiofiles
import yaml

from quadkit import serialization as json
from quadkit.cli.exceptions import CliError, ConfigNotFoundError
from quadkit.config.lib.merge import interpolate_string

_CONFIG_NAMES = ["application.yaml", "application.yml"]


def find_config(
    *,
    explicit_path: Path | None = None,
    start_dir: Path | None = None,
) -> Path:
    """Locate the quadkit config file.

    Args:
        explicit_path: If given, use this path directly.
        start_dir: Directory to start searching from (default: CWD).

    Returns:
        Resolved Path to the config file.

    Raises:
        ConfigNotFoundError: If no config file is found.
    """
    if explicit_path is not None:
        if explicit_path.is_file():
            return explicit_path
        raise ConfigNotFoundError

    env_path = os.environ.get("QK_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        raise ConfigNotFoundError

    current = Path(start_dir) if start_dir else Path.cwd()
    current = current.resolve()

    while True:
        for name in _CONFIG_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    raise ConfigNotFoundError


def _interpolate_env_vars(text: str) -> str:
    """Replace ${VAR} and ${VAR:default} patterns with environment values."""
    return interpolate_string(text)


def _load_yaml_content(path: Path, raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    interpolated = _interpolate_env_vars(raw)
    try:
        data = yaml.safe_load(interpolated)
    except yaml.YAMLError as error:
        raise CliError(
            f"Invalid YAML in {path}",
            causes=[str(error)],
            suggestions=[
                "Check your YAML syntax",
                f'Validate: python -c "import yaml; yaml.safe_load(open({path}))"',
            ],
        ) from error
    return data if isinstance(data, dict) else {}


def load_config_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML config file from synchronous call sites."""
    try:
        return asyncio.run(load_config_yaml_async(path))
    except RuntimeError as error:
        raise CliError(
            "Cannot call load_config_yaml() while an event loop is running",
            causes=[str(error)],
            suggestions=["Use `await load_config_yaml_async(...)` in async code"],
        ) from error


async def load_config_yaml_async(path: Path) -> dict[str, Any]:
    """Load and parse a YAML config file asynchronously with env interpolation."""
    async with aiofiles.open(path) as file_handle:
        raw = await file_handle.read()
    return _load_yaml_content(path, raw)


async def save_config_yaml_async(
    path: Path,
    config: dict[str, Any],
    *,
    header: str | None = None,
) -> None:
    """Persist YAML configuration data asynchronously."""
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    body = yaml.safe_dump(config, sort_keys=False)
    content = (header or "") + body
    async with aiofiles.open(path, "w") as file_handle:
        await file_handle.write(content)


class ConfigLoader:
    """Async config file loader using aiofiles for non-blocking I/O."""

    async def load_config(self, path: Path) -> dict[str, Any]:
        """Load and parse a JSON config file asynchronously."""
        async with aiofiles.open(path, "rb") as file_handle:
            content = await file_handle.read()
        decoded = json.loads(content)
        if isinstance(decoded, dict):
            return cast("dict[str, Any]", decoded)
        raise ValueError("Config JSON root must be an object")

    async def save_config(self, path: Path, config: dict[str, Any]) -> None:
        """Save config to a JSON file asynchronously."""
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        content: Any = json.dumps(config)
        if isinstance(content, bytes):
            async with aiofiles.open(path, "wb") as file_handle:
                await file_handle.write(content)
            return
        if isinstance(content, str):
            async with aiofiles.open(path, "w") as file_handle:
                await file_handle.write(content)
            return
        raise TypeError("Unsupported serialized config payload type")


__all__ = [
    "ConfigLoader",
    "find_config",
    "load_config_yaml",
    "load_config_yaml_async",
    "save_config_yaml_async",
]
