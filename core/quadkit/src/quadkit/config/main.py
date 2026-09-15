"""Main Quadkit configuration class."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import os
from typing import Any, ClassVar, TypeVar, cast, overload

from quadkit.app.config.discovery import ModuleDiscoveryConfig
from quadkit.app.config.models import AppConfig, HealthConfig
from quadkit.config.base import (
    BaseConfig,
    _field_leaf_names,
    _prune_unknown_config_keys,
    _redact_dict,
    _unknown_config_keys,
)
from quadkit.config.constants import SECRET_FIELD_PATTERNS
from quadkit.config.exceptions import ConfigSourceError
from quadkit.config.lib import ConfigRegistry
from quadkit.config.lib.merge import deep_merge
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.logging import get_logger
from quadkit.logging.config import LoggingConfig
from quadkit.validation import ConfigDict, Field, model_validator

T = TypeVar("T")


@dataclass(init=False)
class QuadkitConfig(BaseConfig):
    """Main Quadkit configuration.

    Sections are declared via typed fields.
    Plugin sections are discovered via entry points at boot time.
    Use ``get_section()`` for dynamic access to plugin sections.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    app_name: str = Field(default="quadkit-app", description="Application name")
    app: AppConfig = Field(default_factory=AppConfig)
    debug: bool = Field(
        default=False,
        description="Enable debug mode. Also toggled by the QK_DEBUG env var.",
    )
    env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment (development, staging, production, test).",
    )
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    modules: list[str] = Field(default_factory=list, description="Enabled modules")
    discovery: ModuleDiscoveryConfig = Field(default_factory=ModuleDiscoveryConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)

    # Instance-based registry for extensions (Injected by provider)
    _config_registry: ConfigRegistry | None = None

    @model_validator(mode="before")
    @classmethod
    def _fold_quadkit_env_section(cls, data: Any) -> Any:
        """Fold the ``quadkit`` env section into root-level fields.

        ``QK_QUADKIT__*`` env vars arrive (via
        :class:`~quadkit.config.lib.EnvironmentConfigSource`) nested under a
        ``quadkit`` key in the merged load dict.  This root config validates
        the whole dict (``config_section=None``), so the section must be
        deep-merged into the top level for fields such as ``debug`` and
        ``logging`` to be populated.  Extension sections (``db``, ``cache``,
        ``monitor``, ...) are left in ``model_extra`` for ``get_section()``.
        The typed ``app`` section accepts both the canonical ``app.name``
        spelling and the legacy ``app_name`` spelling.

        Args:
            data: Raw config dict before field validation.

        Returns:
            The same dict with the ``quadkit`` section folded into the root
            and application-name aliases normalized.
        """
        if not isinstance(data, dict):
            return data
        section = data.get("quadkit")
        if isinstance(section, dict):
            deep_merge(data, section)
            data.pop("quadkit", None)

        app_section = data.get("app")
        root_name = data.get("app_name")
        if isinstance(app_section, dict):
            normalized_app = dict(app_section)
            app_name = normalized_app.get(
                "name", normalized_app.get("app_name", root_name)
            )
            if app_name is not None:
                # ``app.name`` is the public nested spelling. Keep both names
                # in the model so existing AppConfig consumers remain valid.
                normalized_app["name"] = app_name
                normalized_app["app_name"] = app_name
                data["app_name"] = app_name
            for field_name in ("debug", "env"):
                if field_name in normalized_app:
                    # The flat fields remain compatibility aliases used by
                    # application validation and logging.
                    data[field_name] = normalized_app[field_name]
            data["app"] = normalized_app
        elif root_name is not None:
            data["app"] = {"name": root_name, "app_name": root_name}
        return data

    @property
    def environment(self) -> Environment:
        """The active deployment environment."""
        return self.env

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
        return self.debug

    @overload
    def get_section(
        self, name: str, model_cls: None = None
    ) -> dict[str, Any] | None: ...

    @overload
    def get_section(self, name: str, model_cls: type[T]) -> T: ...

    def get_section(
        self, name: str, model_cls: type[T] | None = None
    ) -> T | dict[str, Any] | None:
        """Get a configuration section coerced into a specific model.

        Returns ``None`` for an absent section when *model_cls* is not
        supplied; with *model_cls*, an absent section yields ``model_cls()``
        defaults.
        """
        # Support dotted path traversal (e.g. "ai.rag" → config["ai"]["rag"])
        if "." in name:
            parent_key, child_key = name.split(".", 1)
            parent: Any = self.get_section(parent_key)
            if isinstance(parent, dict):
                data = parent.get(child_key)
            else:
                data = getattr(parent, child_key, None)
        else:
            data = getattr(self, name, None)
            _model_extra = getattr(self, "model_extra", {}) or {}
            if data is None and _model_extra:
                data = _model_extra.get(name)

        if model_cls is None and self._config_registry:
            model_cls = self._config_registry.get(name)

        if model_cls is None:
            # Return the raw dict/attribute value, or None when absent.
            if data is None:
                return None
            return cast("T | dict[str, Any]", data)

        if isinstance(data, model_cls):
            return data
        if not isinstance(data, dict):
            if data is None:
                logger.debug(
                    "config.section_defaults",
                    section=name,
                    model=model_cls.__name__,
                    reason="section absent from yaml; code defaults apply",
                )
            return model_cls()

        unknown = _unknown_config_keys(data, model_cls)
        if unknown:
            leaves = [p.rsplit(".", 1)[-1] for p in _field_leaf_names(model_cls)]
            hints = []
            for key in unknown:
                near = difflib.get_close_matches(
                    key.rsplit(".", 1)[-1], leaves, n=1, cutoff=0.6
                )
                if near:
                    hints.append(f"{key} — did you mean '{near[0]}'?")
            allow = os.environ.get("QK_CONFIG_ALLOW_UNKNOWN", "").lower() in {
                "1",
                "true",
                "yes",
            }
            detail = ", ".join(unknown)
            hint_text = (" Suggestions: " + "; ".join(hints)) if hints else ""
            bypass = " Set QK_CONFIG_ALLOW_UNKNOWN=true to bypass."
            if allow:
                logger.warning(
                    "config.unknown_keys_allowed",
                    section=name,
                    keys=detail,
                )
                data = _prune_unknown_config_keys(data, model_cls)
            else:
                raise ConfigSourceError(
                    f"Unknown configuration key(s) in section '{name}': "
                    f"{detail}.{hint_text}{bypass}"
                )

        logger.debug(
            "config.section_bound",
            section=name,
            model=model_cls.__name__,
            keys=len(data),
        )
        return model_cls(**data)

    def has_section(self, name: str) -> bool:
        """Check whether a configuration section exists.

        Looks for a field attribute or an entry in ``model_extra``.

        Args:
            name: Section name to check.

        Returns:
            True if the section is present.
        """
        if hasattr(self, name) and getattr(self, name) is not None:
            return True
        _model_extra = getattr(self, "model_extra", {}) or {}
        return bool(_model_extra and name in _model_extra)

    def to_dict(self, *, redact_secrets: bool = True) -> dict[str, Any]:
        """Serialize the config to a plain dict, optionally redacting secrets.

        Fields whose names contain common secret patterns (e.g. ``password``,
        ``token``, ``api_key``) are replaced with ``"***"``.

        Args:
            redact_secrets: Whether to redact secret-looking fields.

        Returns:
            A dict representation of the configuration.
        """
        data = self.model_dump() if hasattr(self, "model_dump") else vars(self).copy()

        if redact_secrets:
            _redact_dict(data, SECRET_FIELD_PATTERNS)
        return data

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Validate QuadkitConfig-specific production constraints.

        Blocks ``debug=True`` in production.

        Args:
            env: Target environment; defaults to ``self.env``.

        Returns:
            A list of :class:`~quadkit.contracts.core.config.ConfigIssue`.
        """
        resolved = env or self.env
        issues: list[ConfigIssue] = []

        if resolved == Environment.PRODUCTION and self.debug:
            issues.append(
                ConfigIssue(
                    field="debug",
                    message="debug=True is not allowed in production",
                    severity="error",
                    suggestion="Set debug=False or remove the QK_DEBUG env var",
                )
            )

        return issues


__all__ = ["QuadkitConfig"]

logger = get_logger(__name__)
