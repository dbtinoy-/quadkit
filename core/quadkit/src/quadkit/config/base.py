"""Base configuration class for Quadkit Framework."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Self

from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.domain import DomainModel
from quadkit.logging import get_logger
from quadkit.validation import ConfigDict

logger = get_logger(__name__)
_MISSING = object()


@dataclass(init=False)
class BaseConfig(DomainModel):
    """Base configuration class for all Quadkit configs.

    Features:
    - Environment variable override (QK_ prefix)
    - YAML file loading via explicit ``from_yaml()``
    - Testing support via ``from_dict()``
    - Field validation via ``@field_validator`` / ``@model_validator``
    - Type coercion (str -> bool/int/float) for env var values
    - Extra kwargs are silently ignored (safe default)

    Backed by ``DomainModel`` (stdlib dataclasses), NOT pydantic.

    Usage::

        @dataclass(init=False)
        class MyConfig(BaseConfig):
            database_url: str = "sqlite:///./app.db"
            debug: bool = False

        # Load from YAML
        config = MyConfig.from_yaml("application.yaml")

        # Load from dict (testing)
        config = MyConfig.from_dict({"database_url": "sqlite:///:memory:"})
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    #: The top-level YAML/env-var section key for this config class.
    #: Subclasses declare this once (e.g. ``config_section = "cache"``) so
    #: callers never need to pass ``section=`` explicitly.  Matches the key
    #: after the ``QK_`` prefix in env vars (``QK_CACHE__`` → ``"cache"``).
    #: When empty (the default on ``BaseConfig``), the entire merged dict
    #: is validated as-is — suitable when the YAML file is dedicated to a
    #: single package.
    config_section: ClassVar[str] = ""

    @classmethod
    def from_yaml(
        cls,
        path: str | Path = "application.yaml",
        *,
        profile: str | None = None,
        env_override: bool = True,
        section: str | None = None,
    ) -> Self:
        """Load config from a YAML file with env var interpolation.

        This is THE canonical way to load Quadkit configuration.  The loading
        order is deterministic and explicit:

        1. YAML file values (base layer)
        2. Profile overlay (if QK_PROFILE is set or provided)
        3. ``QK_*`` environment variables override YAML values

        When *env_override* is ``False``, only the YAML file is loaded — env
        vars are **not** added as a configuration source.

        The *section* key is resolved in this order:

        1. The explicit *section* argument (highest priority).
        2. :attr:`config_section` declared on the subclass.
        3. ``None`` — the whole merged dict is validated as-is.

        Args:
            path: Path to YAML file. Relative paths resolve from CWD.
            profile: Profile name (overrides QK_PROFILE env var).
            env_override: If True (default), env vars override YAML values.
            section: Override the section key for this call.  When omitted,
                :attr:`config_section` is used automatically.
        """
        from quadkit.config.lib import (
            ConfigLoader,
            EnvironmentConfigSource,
            FileConfigSource,
        )

        loader = ConfigLoader()

        # 1. Base YAML file
        yaml_path = Path(path)
        if not yaml_path.is_absolute():
            yaml_path = Path.cwd() / yaml_path
        if yaml_path.exists():
            loader.add_source(FileConfigSource(yaml_path))
        else:
            logger.info(
                "config.defaults_only",
                path=str(yaml_path),
                hint="create application.yaml or set QK_* env vars",
            )

        # 2. Profile overlay
        import os

        resolved_profile = profile or os.environ.get("QK_PROFILE")
        if resolved_profile:
            profile_path = yaml_path.parent / f"application.{resolved_profile}.yaml"
            if profile_path.exists():
                loader.add_source(FileConfigSource(profile_path))

        # 3. Env vars
        if env_override:
            loader.add_source(EnvironmentConfigSource("QK_"))

        raw = loader._collect_sync(None)
        resolved_section = section if section is not None else cls.config_section
        if resolved_section:
            raw = raw.get(resolved_section, {})
        return loader._validate(cls, raw)

    @property
    def environment(self) -> Environment:
        """The active deployment environment.

        Reads from the ``env`` field first; falls back to ``QK_ENV``.
        """
        env_val = getattr(self, "env", None)
        if env_val is not None:
            if isinstance(env_val, Environment):
                return env_val
            return Environment(env_val)
        return Environment.from_env()

    @property
    def is_production(self) -> bool:
        """Return ``True`` when the active environment is production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Return ``True`` when the active environment is development."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_testing(self) -> bool:
        """Return ``True`` when the active environment is testing."""
        return self.environment == Environment.TEST

    @property
    def is_staging(self) -> bool:
        """Return ``True`` when the active environment is staging."""
        return self.environment == Environment.STAGING

    @property
    def is_debug(self) -> bool:
        """Return ``True`` when debug mode is enabled."""
        return getattr(self, "debug", False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key or attribute.

        Args:
            key: Configuration key (e.g., 'app.name' or 'database.url').
            default: Default value if key is not found.
        """
        try:
            if "." not in key:
                return getattr(self, key, default)

            parts = key.split(".")
            val: Any = self
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part, _MISSING)
                    if val is _MISSING:
                        return default
                elif hasattr(val, part):
                    val = getattr(val, part)
                else:
                    return default
            return val
        except (AttributeError, KeyError, TypeError):
            return default

    def has_section(self, name: str) -> bool:
        """Check whether a configuration section exists.

        Args:
            name: Section name to check.

        Returns:
            True if the section is present.
        """
        return hasattr(self, name) and getattr(self, name) is not None

    def to_safe_dict(self) -> dict[str, Any]:
        """Serialize the config to a plain dict with all secrets redacted.

        Fields whose names match :data:`~quadkit.config.constants.SECRET_FIELD_PATTERNS`
        are replaced with ``"***"``.

        Returns:
            A safe, serializable dict representation.
        """
        from quadkit.config.constants import SECRET_FIELD_PATTERNS

        data = self.model_dump() if hasattr(self, "model_dump") else vars(self).copy()
        _redact_dict(data, SECRET_FIELD_PATTERNS)
        return data

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Validate this config for the given deployment environment.

        Subclasses should override this method to add environment-specific
        checks (e.g. blocking debug mode in production).  The base
        implementation always returns an empty list.

        Args:
            env: The target environment.  When ``None`` the active environment
                is resolved via ``Environment.from_env()``.

        Returns:
            A list of :class:`~quadkit.contracts.core.config.ConfigIssue`
            instances.  An empty list means validation passed.
        """
        return []

    @classmethod
    def from_env_profile(
        cls,
        profile: str | None = None,
        *,
        base_path: str | Path = ".",
        section: str | None = None,
    ) -> Self:
        """Load config for a named environment profile.

        Looks for ``application.yaml`` in *base_path* as the base, then
        overlays ``application.{profile}.yaml`` if ``QK_PROFILE`` is set or
        *profile* is given.  ``QK_*`` environment variables are applied last.

        This is the recommended method for **production, staging, Docker,
        Kubernetes, and CI/CD** deployments.  Set ``QK_PROFILE=production``
        in your environment and the right profile file is loaded automatically
        — no code changes needed when promoting between environments.

        Common profiles: ``development``, ``staging``, ``production``, ``test``.
        If *profile* is omitted the ``QK_PROFILE`` environment variable is
        consulted.

        The *section* key is resolved in this order:

        1. The explicit *section* argument (highest priority).
        2. :attr:`config_section` declared on the subclass.
        3. ``None`` — the whole merged dict is validated as-is.

        Args:
            profile: Environment profile name.  When ``None``, the
                ``QK_PROFILE`` env-var is used.
            base_path: Directory containing the profile YAML files.
            section: Override the section key for this call.  When omitted,
                :attr:`config_section` is used automatically.

        Example::

            # Uses cls.config_section automatically — no section= needed
            config = CacheConfig.from_env_profile()

            # Explicit override (e.g. non-standard nesting)
            config = CacheConfig.from_env_profile(section="services.cache")
        """
        return cls.from_yaml(
            Path(base_path) / "application.yaml", profile=profile, section=section
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create config from a plain dict. Useful for testing.

        Args:
            data: Configuration data as a dictionary.

        Example::

            config = MyConfig.from_dict({
                "app": {"name": "test-app"},
                "database": {"url": "sqlite:///:memory:"},
            })
        """
        return cls(**data)


# ── Strict unknown-key detection ────────────────────────────────────────────
def _resolve_nested_model(annotation: object) -> type | None:
    """Return the model type behind ``Optional[Model]``-style annotations."""
    import typing

    if isinstance(annotation, str):
        return None  # forward refs are resolved by get_type_hints upstream
    args = typing.get_args(annotation)
    if args:
        non_none = [a for a in args if a is not type(None)]
        if len(args) == 2 and type(None) in args:
            annotation = non_none[0]
    return annotation if isinstance(annotation, type) else None


def _unknown_config_keys(
    data: dict[str, Any],
    model_cls: type,
    prefix: str = "",
) -> list[str]:
    """Recursively diff *data* against *model_cls* fields.

    Returns dotted paths of keys that the model does not define — the
    canonical signal for typos in ``application.yaml``.
    """
    import typing

    fields = dict(getattr(model_cls, "__dataclass_fields__", {}) or {})
    try:
        hints = typing.get_type_hints(model_cls)
    except Exception:  # noqa: BLE001 — unresolvable refs degrade to flat check
        hints = {}
    for hinted_name in hints:
        fields.setdefault(hinted_name, None)

    unknown: list[str] = []
    for key, value in data.items():
        path = f"{prefix}{key}"
        if key not in fields:
            unknown.append(path)
            continue
        nested = _resolve_nested_model(hints.get(key))
        if (
            nested is not None
            and nested is not model_cls
            and hasattr(nested, "__dataclass_fields__")
            and isinstance(value, dict)
        ):
            unknown.extend(_unknown_config_keys(value, nested, prefix=f"{path}."))

    return unknown


def _prune_unknown_config_keys(
    data: dict[str, Any],
    model_cls: type,
    prefix: str = "",
) -> dict[str, Any]:
    """Return a copy of *data* with unknown keys removed (escape-hatch mode)."""
    fields = getattr(model_cls, "__dataclass_fields__", {})
    import typing

    try:
        hints = typing.get_type_hints(model_cls)
    except Exception:  # noqa: BLE001
        hints = {}

    pruned: dict[str, Any] = {}
    for key, value in data.items():
        if key not in fields:
            continue
        nested = None
        ann = hints.get(key)
        if ann is not None:
            import typing as t

            args = t.get_args(ann)
            if len(args) == 2 and type(None) in args:
                ann = next(a for a in args if a is not type(None))
            nested = ann if isinstance(ann, type) else None
        if (
            nested is not None
            and hasattr(nested, "__dataclass_fields__")
            and isinstance(value, dict)
        ):
            pruned[key] = _prune_unknown_config_keys(
                value, nested, prefix=f"{prefix}{key}."
            )
        else:
            pruned[key] = value
    return pruned


def _field_leaf_names(model_cls: type, prefix: str = "") -> list[str]:
    """All dotted field paths of a config model (for did-you-mean hints)."""
    import dataclasses
    import typing

    try:
        hints = typing.get_type_hints(model_cls)
    except Exception:  # noqa: BLE001
        hints = {}

    leaves: list[str] = []
    for f in dataclasses.fields(model_cls):
        if f.name.startswith("_") or f.name in {"model_config", "config_section"}:
            continue
        path = f"{prefix}{f.name}"
        nested = _resolve_nested_model(hints.get(f.name))
        if f.name.startswith("_") or f.name in {"model_config", "config_section"}:
            continue
        path = f"{prefix}{f.name}"
        if (
            nested is not None
            and nested is not model_cls
            and hasattr(nested, "__dataclass_fields__")
        ):
            leaves.extend(_field_leaf_names(nested, prefix=f"{path}."))
        else:
            leaves.append(path)
    return leaves


def _redact_dict(data: dict[str, Any], patterns: frozenset[str]) -> None:
    """Recursively redact values whose keys match secret patterns in-place."""
    for key, value in data.items():
        if isinstance(value, dict):
            _redact_dict(value, patterns)
        elif any(p in key.lower() for p in patterns):
            data[key] = "***"


__all__ = ["BaseConfig"]
