"""Configuration sources for Quadkit Framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
import argparse
import json  # noqa: TID251 — config loading intentionally uses stdlib json, not quadkit.serialization
import os
from pathlib import Path
from typing import Any, TypeVar

from quadkit.config.lib.merge import deep_merge, interpolate_env_vars
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.logging import get_logger

T = TypeVar("T")


# -- Source base -----------------------------------------------------------


class ConfigSource(ABC):
    """Abstract configuration source."""

    pre_interpolated: bool = False
    """Whether loaded values are already env-resolved.

    When ``True``, :meth:`ConfigLoader._collect_sync` skips
    ``${VAR}`` interpolation for this source's data. Values taken
    directly from the process environment are already resolved; their
    contents may legitimately contain ``${...}``-shaped text (shell
    prompts, scripts) that must not be re-interpreted as placeholders.
    """

    @abstractmethod
    def load_sync(self) -> dict[str, Any]:
        """Load config synchronously."""

    async def load(self) -> dict[str, Any]:
        """Load config asynchronously. Default: delegates to sync."""
        import asyncio

        return await asyncio.to_thread(self.load_sync)

    @abstractmethod
    def get_name(self) -> str:
        """Source name for logging."""


# -- Sources ---------------------------------------------------------------


class EnvironmentConfigSource(ConfigSource):
    """Load from environment variables.

    Variables are lowercased, prefix-stripped, and ``__`` (or the configured
    *nested_delimiter*) is treated as nesting
    (e.g., ``QK__DB__HOST`` → ``{"db": {"host": ...}}``).

    Values are already env-resolved, so they are never re-interpolated.
    """

    pre_interpolated = True

    def __init__(self, prefix: str = "", *, nested_delimiter: str = "__") -> None:
        self._prefix = prefix
        self._delimiter = nested_delimiter

    def load_sync(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        for key, value in os.environ.items():
            if not key.startswith(self._prefix):
                continue

            config_key = key[len(self._prefix) :].lower()
            parsed = self._parse_value(value)

            if self._delimiter in config_key:
                parts = config_key.split(self._delimiter)
                node = config
                for part in parts[:-1]:
                    node = node.setdefault(part, {})
                node[parts[-1]] = parsed
            else:
                config[config_key] = parsed

        return config

    @staticmethod
    def _parse_value(value: str) -> str | int | float:
        """Parse env var strings to numeric types only.

        Boolean coercion is intentionally omitted — Pydantic handles
        it via field type annotations, avoiding the ambiguity where
        ``"0"`` could mean ``False`` or ``0``.
        """
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def get_name(self) -> str:
        return f"environment({self._prefix})"


class FileConfigSource(ConfigSource):
    """Load from a JSON or YAML file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load_sync(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            contents = self._path.read_text(encoding="utf-8")
            return self._parse(contents)
        except (OSError, UnicodeDecodeError) as err:
            raise ConfigurationError(
                f"Failed to load config from {self._path}: {err}",
            ) from err

    async def load(self) -> dict[str, Any]:
        import anyio

        p = anyio.Path(self._path)
        if not await p.exists():
            return {}
        try:
            contents = await p.read_text(encoding="utf-8")
            return self._parse(contents)
        except (OSError, UnicodeDecodeError) as err:
            raise ConfigurationError(
                f"Failed to load config from {self._path}: {err}",
            ) from err

    def _parse(self, contents: str) -> dict[str, Any]:
        """Parse JSON or YAML content."""
        if self._path.suffix.lower() == ".json":
            data = json.loads(contents)
            if not isinstance(data, dict):
                raise ConfigurationError(
                    f"Config file {self._path} must contain a JSON object",
                )
            return data

        # Try JSON first, then YAML
        try:
            data = json.loads(contents)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        try:
            import yaml

            data = yaml.safe_load(contents)
            if not isinstance(data, dict):
                raise ConfigurationError(
                    f"Config file {self._path} must contain a mapping",
                )
            return data
        except ImportError as err:
            raise ConfigurationError(
                f"YAML support not available for {self._path}. "
                "Install PyYAML: pip install pyyaml",
            ) from err

    def get_name(self) -> str:
        return f"file({self._path})"


class DotEnvSource(ConfigSource):
    """Load from a ``.env`` file into environment variables then re-read them.

    Reads ``KEY=VALUE`` pairs from the file and populates ``os.environ``
    before delegating to :class:`EnvironmentConfigSource`.  Variables that
    are already set in the environment are **not** overwritten (unless
    *override* is ``True``).

    Args:
        path: Path to the ``.env`` file (default: ``".env"`` in CWD).
        prefix: Optional env-var prefix to filter (forwarded to the inner
            ``EnvironmentConfigSource``).
        override: When ``True``, values from the file overwrite existing env
            variables.  Defaults to ``False``.
        nested_delimiter: Delimiter used to represent nesting in variable
            names (default: ``"__"``).
    """

    def __init__(
        self,
        path: str | Path = ".env",
        *,
        prefix: str = "",
        override: bool = False,
        nested_delimiter: str = "__",
    ) -> None:
        self._path = Path(path)
        self._prefix = prefix
        self._override = override
        self._nested_delimiter = nested_delimiter

    def load_sync(self) -> dict[str, Any]:
        self._populate_env()
        return EnvironmentConfigSource(
            self._prefix, nested_delimiter=self._nested_delimiter
        ).load_sync()

    def _populate_env(self) -> None:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if self._override or key not in os.environ:
                os.environ[key] = value

    def get_name(self) -> str:
        return f"dotenv({self._path})"


class DirectoryConfigSource(ConfigSource):
    """Load and merge all YAML/JSON files from a directory."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._logger = get_logger(__name__)

    def load_sync(self) -> dict[str, Any]:
        if not self._directory.is_dir():
            return {}

        merged: dict[str, Any] = {}
        for path in sorted(self._directory.iterdir()):
            if path.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            if path.name.startswith((".", "_")):
                continue

            try:
                data = FileConfigSource(path).load_sync()
                if not data:
                    continue

                stem = path.stem.replace("-", "_")
                if len(data) == 1 and stem in data:
                    deep_merge(merged, data)
                elif stem not in data:
                    deep_merge(merged, {stem: data})
                else:
                    deep_merge(merged, data)
            except (OSError, json.JSONDecodeError, ConfigurationError):
                self._logger.warning(
                    "Failed to load config from %s",
                    path,
                    exc_info=True,
                )

        return merged

    def get_name(self) -> str:
        return f"directory({self._directory})"


class CliConfigSource(ConfigSource):
    """Load from command-line arguments.

    Args:
        args: Pre-parsed argparse.Namespace. If not provided, parses sys.argv.
        parser: External argparse.ArgumentParser to use. If provided, uses this
            parser instead of creating a default one. Useful for integrating
            with existing CLI frameworks like Click or Typer.
    """

    def __init__(
        self,
        args: argparse.Namespace | None = None,
        parser: argparse.ArgumentParser | None = None,
    ) -> None:
        self._args = args
        self._parser = parser

    def load_sync(self) -> dict[str, Any]:
        args = self._args or self._parse_args()
        config: dict[str, Any] = {}

        config_path = getattr(args, "config", None)
        if config_path:
            config.update(FileConfigSource(config_path).load_sync())

        env_prefix = getattr(args, "env_prefix", None)
        if env_prefix:
            config.update(EnvironmentConfigSource(env_prefix).load_sync())

        return config

    def _parse_args(self) -> argparse.Namespace:
        if self._parser is not None:
            return self._parser.parse_args()
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--config", type=str, default=None)
        parser.add_argument("--env-prefix", type=str, default=None)
        args, _ = parser.parse_known_args()
        return args

    def get_name(self) -> str:
        return "cli"


# -- ConfigLoader ----------------------------------------------------------


class ConfigLoader:
    """Loads, merges, interpolates, and validates configuration."""

    def __init__(self) -> None:
        self._sources: list[ConfigSource] = []
        self._logger = get_logger(__name__)

    def add_source(self, source: ConfigSource) -> None:
        self._sources.append(source)

    def load_sync(
        self,
        schema: type[T],
        sources: list[ConfigSource] | None = None,
    ) -> T:
        """Load and validate config synchronously."""
        merged = self._collect_sync(sources)
        return self._validate(schema, merged)

    async def load(
        self,
        schema: type[T],
        sources: list[ConfigSource] | None = None,
    ) -> T:
        """Load and validate config asynchronously."""
        merged = await self._collect(sources)
        return self._validate(schema, merged)

    # -- Internal ----------------------------------------------------------

    def _get_sources(self, sources: list[ConfigSource] | None) -> list[ConfigSource]:
        """Get sources to use, with defaults if none provided."""
        if sources:
            return sources
        if self._sources:
            return self._sources
        return [
            EnvironmentConfigSource(),
            FileConfigSource(Path.cwd() / "config.json"),
            FileConfigSource(Path.cwd() / "config.yaml"),
        ]

    def _collect_sync(self, sources: list[ConfigSource] | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for source in self._get_sources(sources):
            try:
                data = source.load_sync()
            except (json.JSONDecodeError, ConfigurationError):
                # Malformed config content is a hard error.  Swallowing it
                # would silently boot the app on partial defaults, so fail
                # fast (consistent with ${VAR} interpolation, QK_ERR_CFG_001).
                raise
            except Exception:  # noqa: BLE001 — genuinely optional sources (e.g. a network-backed source that is momentarily unreachable) may be skipped; driver errors are not builtin OSError types. FileConfigSource wraps its own read errors in ConfigurationError, so file problems still fail fast.
                self._logger.exception(
                    "Failed to load config from %s",
                    source.get_name(),
                )
                continue
            if not source.pre_interpolated:
                # Authored sources may reference env vars via ${VAR};
                # unresolved references fail fast (QK_ERR_CFG_001).
                interpolate_env_vars(data)
            deep_merge(merged, data)
        return merged

    async def _collect(
        self,
        sources: list[ConfigSource] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for source in self._get_sources(sources):
            try:
                data = await source.load()
            except (json.JSONDecodeError, ConfigurationError):
                # Malformed config content is a hard error — fail fast
                # instead of booting on partial defaults (see _collect_sync).
                raise
            except Exception:  # noqa: BLE001 — optional source load failures (including driver errors) are logged and skipped
                self._logger.exception(
                    "Failed to load config from %s",
                    source.get_name(),
                )
                continue
            if not source.pre_interpolated:
                interpolate_env_vars(data)
            deep_merge(merged, data)
        return merged

    def _validate(self, schema: type[T], config: dict[str, Any]) -> T:
        try:
            return schema(**config)
        except ValidationError as err:
            raise ConfigurationError.from_validation_error(err) from err


__all__ = [
    "CliConfigSource",
    "ConfigLoader",
    "ConfigSource",
    "ConfigurationError",
    "DirectoryConfigSource",
    "DotEnvSource",
    "EnvironmentConfigSource",
    "FileConfigSource",
]
