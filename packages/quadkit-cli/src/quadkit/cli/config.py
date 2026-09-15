from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from quadkit.cli import constants as cli_const
from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class CLIConfig(BaseConfig):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    config_section: ClassVar[str] = "cli"
    name: str = "cli"
    enabled: bool = True

    env: Environment | None = Field(None, description="Deployment environment")
    default_template: str = Field(default="web-api")
    default_database: str = Field(default="postgres")
    color: bool = Field(default=True)
    verbose: bool = Field(default=False)


class ConfigManager:
    config_path = Path.home() / cli_const.DEFAULT_CONFIG_FILE

    @classmethod
    def load(cls) -> CLIConfig:
        if not cls.config_path.exists():
            return CLIConfig()

        with open(cls.config_path, "rb") as f:
            data = tomllib.load(f)
            return CLIConfig(**data.get("cli", {}))

    @classmethod
    def save(cls, config: CLIConfig) -> None:
        """Persist CLI configuration to disk in TOML format.

        Preserves existing non-cli sections in the config file.
        Creates parent directories if they do not exist.

        Args:
            config: CLI configuration to save.
        """
        # Read existing file to preserve other sections
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redef]

        existing_data: dict[str, object] = {}
        if cls.config_path.exists():
            try:
                with open(cls.config_path, "rb") as f:
                    existing_data = tomllib.load(f)
            except Exception:  # noqa: BLE001
                existing_data = {}

        # Build [cli] section - use model_dump to get all fields automatically
        cli_data: dict[str, object] = config.model_dump()

        # TOML has no null literal: drop unset (None) fields so they fall
        # back to their defaults on load.  Keeps tomli_w from raising
        # TypeError and the manual writer from emitting the corrupting
        # string "None".
        cli_data = {k: v for k, v in cli_data.items() if v is not None}

        # Merge - overwrite [cli] while keeping everything else
        existing_data["cli"] = cli_data

        # Create parent directories if needed
        cls.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write TOML
        try:
            import tomli_w

            with open(cls.config_path, "wb") as f:
                tomli_w.dump(existing_data, f)
        except ImportError:
            # Fallback: manual TOML serialization
            with open(cls.config_path, "w") as f:
                for section_name, section_data in existing_data.items():
                    if isinstance(section_data, dict):
                        f.write(f"[{section_name}]\n")
                        for key, value in section_data.items():
                            literal = _toml_value(value)
                            if literal is not None:
                                f.write(f"{key} = {literal}\n")
                        f.write("\n")


def _toml_value(value: object) -> str | None:
    """Serialize a Python value to a TOML literal.

    ``None`` has no TOML literal — return ``None`` so the caller can omit
    the key entirely (on load the field falls back to its default) instead
    of writing the corrupting string ``"None"``.

    Args:
        value: Value to serialize.

    Returns:
        TOML literal, or ``None`` for values that must be omitted.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


__all__ = ["CLIConfig", "ConfigManager"]
