"""Unit tests for the config module main classes."""

from quadkit.config import BaseConfig, ConfigSourceType, QuadkitConfig
from quadkit.config.constants import (
    DEFAULT_CONFIG_FILENAMES,
    DEFAULT_ENV_VAR_PREFIX,
    DEFAULT_RELOAD_INTERVAL,
    INSECURE_SECRET_VALUES,
    SECRET_FIELD_PATTERNS,
    SUPPORTED_FORMATS,
)


class TestConfigSourceType:
    """Tests for ConfigSourceType enum."""

    def test_file_value(self) -> None:
        """Test FILE enum value."""
        assert ConfigSourceType.FILE == "file"

    def test_environment_value(self) -> None:
        """Test ENVIRONMENT enum value."""
        assert ConfigSourceType.ENVIRONMENT == "environment"

    def test_cli_value(self) -> None:
        """Test CLI enum value."""
        assert ConfigSourceType.CLI == "cli"

    def test_directory_value(self) -> None:
        """Test DIRECTORY enum value."""
        assert ConfigSourceType.DIRECTORY == "directory"

    def test_memory_value(self) -> None:
        """Test MEMORY enum value."""
        assert ConfigSourceType.MEMORY == "memory"


class TestBaseConfig:
    """Tests for BaseConfig base class."""

    def test_is_dataclass(self) -> None:
        """Test that BaseConfig is a dataclass."""
        config = BaseConfig.from_dict({})
        assert hasattr(config, "model_dump")

    def test_from_dict_creates_instance(self) -> None:
        """Test from_dict creates a valid instance."""
        config = BaseConfig.from_dict({"app_name": "test-app"})
        assert isinstance(config, BaseConfig)

    def test_from_dict_with_extra_fields(self) -> None:
        """Test from_dict ignores extra fields."""
        config = BaseConfig.from_dict({"unknown_field": "ignored"})
        assert isinstance(config, BaseConfig)

    def test_environment_property(self) -> None:
        """Test environment property returns Environment."""
        config = BaseConfig.from_dict({})
        env = config.environment
        assert str(env) in ("development", "staging", "production", "test")

    def test_get_returns_default_for_missing_key(self) -> None:
        """Test get returns default for missing keys."""
        config = BaseConfig.from_dict({})
        assert config.get("nonexistent", "default") == "default"

    def test_get_returns_attribute_value(self) -> None:
        """Test get returns attribute value."""
        config = BaseConfig.from_dict({})
        config.app_name = "test-app"
        assert config.get("app_name") == "test-app"

    def test_get_returns_default_for_missing_nested_dict_leaf(self) -> None:
        """A missing leaf in a present dict still uses the caller default."""
        config = QuadkitConfig.from_dict({})
        config.app = {"health_check_timeout": 2.0}

        assert config.get("app.shutdown_timeout", 30.0) == 30.0

    def test_get_preserves_explicit_none_nested_dict_value(self) -> None:
        """An explicit null remains distinguishable from a missing leaf."""
        config = QuadkitConfig.from_dict({})
        config.app = {"shutdown_timeout": None}

        assert config.get("app.shutdown_timeout", 30.0) is None

    def test_has_section_returns_false_for_missing(self) -> None:
        """Test has_section returns False for missing section."""
        config = BaseConfig.from_dict({})
        assert config.has_section("missing-section") is False

    def test_to_safe_dict_returns_dict(self) -> None:
        """Test to_safe_dict returns a dict."""
        config = BaseConfig.from_dict({})
        result = config.to_safe_dict()
        assert isinstance(result, dict)

    def test_validate_for_environment_returns_empty_list(self) -> None:
        """Test validate_for_environment returns empty list."""
        config = BaseConfig.from_dict({})
        issues = config.validate_for_environment()
        assert issues == []


class TestQuadkitConfig:
    """Tests for QuadkitConfig main class."""

    def test_default_app_name(self) -> None:
        """Test default app name."""
        config = QuadkitConfig.from_dict({})
        assert config.app_name == "quadkit-app"

    def test_app_section_is_typed_and_uses_defaults(self) -> None:
        """The application lifecycle section is bound to AppConfig."""
        from quadkit.app.config.models import AppConfig

        config = QuadkitConfig.from_dict({})

        assert isinstance(config.app, AppConfig)
        assert config.app.shutdown_timeout == 30.0
        assert config.app.health_check_timeout == 5.0

    def test_app_section_accepts_name_alias_and_coerces_values(self) -> None:
        """Nested app.name is compatible with legacy app_name consumers."""
        from quadkit.app.config.models import AppConfig

        config = QuadkitConfig.from_dict(
            {
                "app": {
                    "name": "orders",
                    "debug": "false",
                    "env": "staging",
                    "shutdown_timeout": "45",
                }
            }
        )

        assert isinstance(config.app, AppConfig)
        assert config.app.name == "orders"
        assert config.app.app_name == "orders"
        assert config.app_name == "orders"
        assert config.app.debug is False
        assert config.app.env == "staging"
        assert config.debug is False
        assert config.env.value == "staging"
        assert config.app.shutdown_timeout == 45.0

    def test_default_debug_false(self) -> None:
        """Test default debug is False."""
        config = QuadkitConfig.from_dict({})
        assert config.debug is False

    def test_default_logging_config(self) -> None:
        """Test default logging config is set."""
        config = QuadkitConfig.from_dict({})
        assert config.logging is not None

    def test_environment_property_overrides_field(self) -> None:
        """Test environment property returns env field value."""
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict({"env": Environment.DEVELOPMENT})
        assert config.environment == Environment.DEVELOPMENT

    def test_environment_convenience_properties(self) -> None:
        """Test environment convenience properties mirror the resolved env."""
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict(
            {"env": Environment.STAGING, "debug": True},
        )

        assert config.is_staging is True
        assert config.is_production is False
        assert config.is_development is False
        assert config.is_testing is False
        assert config.is_debug is True

    def test_get_section_returns_none_for_missing(self) -> None:
        """Test get_section returns None for a missing section."""
        config = QuadkitConfig.from_dict({})
        assert config.get_section("nonexistent") is None

    def test_has_section_false_for_missing(self) -> None:
        """Test has_section returns False for missing section."""
        config = QuadkitConfig.from_dict({})
        assert config.has_section("nonexistent") is False

    def test_to_dict_returns_dict(self) -> None:
        """Test to_dict returns a dict."""
        config = QuadkitConfig.from_dict({})
        result = config.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_redacts_secrets_by_default(self) -> None:
        """Test to_dict redacts secrets by default."""
        config = QuadkitConfig.from_dict({"api_key": "secret123"})
        result = config.to_dict()
        assert result.get("api_key") == "***"

    def test_to_dict_no_redact_when_disabled(self) -> None:
        """Test to_dict does not redact when redact_secrets=False."""
        config = QuadkitConfig.from_dict({"api_key": "secret123"})
        result = config.to_dict(redact_secrets=False)
        assert result.get("api_key") == "secret123"

    def test_validate_for_environment_allows_debug_in_dev(self) -> None:
        """Test debug=True is allowed in development."""
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict(
            {"debug": True, "env": Environment.DEVELOPMENT}
        )
        issues = config.validate_for_environment()
        assert issues == []

    def test_validate_for_environment_blocks_debug_in_prod(self) -> None:
        """Test debug=True is blocked in production."""
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict(
            {"debug": True, "env": Environment.PRODUCTION}
        )
        issues = config.validate_for_environment()
        assert len(issues) == 1
        assert issues[0].field == "debug"

    def test_extra_fields_allowed(self) -> None:
        """Test extra fields are allowed via model_extra."""
        config = QuadkitConfig.from_dict({"extra_field": "value"})
        assert config.model_extra.get("extra_field") == "value"


class TestConfigConstants:
    """Tests for config constants."""

    def test_default_config_filenames(self) -> None:
        """Test default config filenames."""
        assert "application.yaml" in DEFAULT_CONFIG_FILENAMES
        assert "application.yml" in DEFAULT_CONFIG_FILENAMES

    def test_default_env_var_prefix(self) -> None:
        """Test default env var prefix."""
        assert DEFAULT_ENV_VAR_PREFIX == "QK_"

    def test_default_reload_interval(self) -> None:
        """Test default reload interval."""
        assert DEFAULT_RELOAD_INTERVAL == 30.0

    def test_supported_formats(self) -> None:
        """Test supported formats."""
        assert "yaml" in SUPPORTED_FORMATS
        assert "yml" in SUPPORTED_FORMATS
        assert "json" in SUPPORTED_FORMATS

    def test_insecure_secret_values(self) -> None:
        """Test insecure secret values set."""
        assert "password" in INSECURE_SECRET_VALUES
        assert "secret" in INSECURE_SECRET_VALUES
        assert "change-me" in INSECURE_SECRET_VALUES

    def test_secret_field_patterns(self) -> None:
        """Test secret field patterns set."""
        assert "password" in SECRET_FIELD_PATTERNS
        assert "secret" in SECRET_FIELD_PATTERNS
        assert "token" in SECRET_FIELD_PATTERNS
        assert "api_key" in SECRET_FIELD_PATTERNS
