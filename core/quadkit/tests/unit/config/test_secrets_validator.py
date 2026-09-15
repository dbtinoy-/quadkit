"""Tests for boot-time secrets validation (QK-007).

Covers:
- PRODUCTION + placeholder value → raises ConfigurationError
- PRODUCTION + short value → raises ConfigurationError
- PRODUCTION + valid value → no exception
- DEVELOPMENT + placeholder value (allow_placeholders_in_dev=True) → warns, boots
- DEVELOPMENT + strict=True override → enforces strict in dev
- Custom placeholder set respected
- Per-secret-name length override respected
"""

from __future__ import annotations

import pytest

from quadkit.config.secrets import (
    DEFAULT_MIN_LENGTHS,
    DEFAULT_PLACEHOLDER_VALUES,
    SecretsPolicy,
    SecretsValidator,
    SecretsValidatorProtocol,
    SecretViolation,
)
from quadkit.contracts.core.config import Environment
from quadkit.contracts.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# SecretsPolicy.for_environment
# ---------------------------------------------------------------------------


class TestSecretsPolicyForEnvironment:
    def test_production_is_strict(self) -> None:
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        assert policy.strict is True
        assert policy.allow_placeholders_in_dev is False

    def test_staging_is_strict(self) -> None:
        policy = SecretsPolicy.for_environment(Environment.STAGING)
        assert policy.strict is True
        assert policy.allow_placeholders_in_dev is False

    def test_development_is_non_strict(self) -> None:
        policy = SecretsPolicy.for_environment(Environment.DEVELOPMENT)
        assert policy.strict is False
        assert policy.allow_placeholders_in_dev is True

    def test_test_is_non_strict(self) -> None:
        policy = SecretsPolicy.for_environment(Environment.TEST)
        assert policy.strict is False
        assert policy.allow_placeholders_in_dev is True


# ---------------------------------------------------------------------------
# SecretsPolicy.effective_min_lengths
# ---------------------------------------------------------------------------


class TestEffectiveMinLengths:
    def test_defaults_present(self) -> None:
        policy = SecretsPolicy()
        lengths = policy.effective_min_lengths()
        assert "jwt_secret" in lengths
        assert lengths["jwt_secret"] == 32

    def test_override_replaces_default(self) -> None:
        policy = SecretsPolicy(min_lengths={"jwt_secret": 64})
        assert policy.effective_min_lengths()["jwt_secret"] == 64

    def test_extra_key_added(self) -> None:
        policy = SecretsPolicy(min_lengths={"my_custom_key": 20})
        lengths = policy.effective_min_lengths()
        assert lengths["my_custom_key"] == 20
        # defaults still present
        assert "jwt_secret" in lengths


# ---------------------------------------------------------------------------
# SecretsValidator — strict mode (PRODUCTION)
# ---------------------------------------------------------------------------


class TestSecretsValidatorStrictMode:
    """Strict mode: any violation must raise ConfigurationError."""

    @pytest.fixture
    def production_validator(self) -> SecretsValidator:
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        return SecretsValidator(policy)

    def test_valid_secret_passes(self, production_validator: SecretsValidator) -> None:
        production_validator.validate({"JWT_SECRET": "a" * 32})  # no exception

    def test_placeholder_value_raises(
        self, production_validator: SecretsValidator
    ) -> None:
        with pytest.raises(ConfigurationError, match="placeholder"):
            production_validator.validate({"JWT_SECRET": "change-me"})

    def test_empty_string_raises(self, production_validator: SecretsValidator) -> None:
        with pytest.raises(ConfigurationError):
            production_validator.validate({"JWT_SECRET": ""})

    def test_short_jwt_secret_raises(
        self, production_validator: SecretsValidator
    ) -> None:
        # jwt_secret requires ≥ 32 chars
        with pytest.raises(ConfigurationError, match="too short"):
            production_validator.validate({"JWT_SECRET": "short"})

    def test_short_oauth_secret_raises(
        self, production_validator: SecretsValidator
    ) -> None:
        # client_secret requires ≥ 16 chars
        with pytest.raises(ConfigurationError, match="too short"):
            production_validator.validate({"OAUTH_CLIENT_SECRET": "tiny"})

    def test_multiple_violations_all_reported(
        self, production_validator: SecretsValidator
    ) -> None:
        with pytest.raises(ConfigurationError) as exc_info:
            production_validator.validate(
                {
                    "JWT_SECRET": "change-me",
                    "OAUTH_CLIENT_SECRET": "x",
                }
            )
        msg = str(exc_info.value)
        assert "JWT_SECRET" in msg
        assert "OAUTH_CLIENT_SECRET" in msg

    def test_non_secret_name_no_length_constraint(
        self, production_validator: SecretsValidator
    ) -> None:
        # "DATABASE_URL" does not match any min_length pattern — no error
        production_validator.validate({"DATABASE_URL": "short"})

    def test_exact_minimum_length_passes(
        self, production_validator: SecretsValidator
    ) -> None:
        production_validator.validate({"JWT_SECRET": "a" * 32})


# ---------------------------------------------------------------------------
# SecretsValidator — non-strict mode (DEVELOPMENT, allow_placeholders_in_dev)
# ---------------------------------------------------------------------------


class TestSecretsValidatorNonStrictMode:
    """Non-strict mode: violations are logged as warnings, boot continues."""

    @pytest.fixture
    def dev_validator(self) -> SecretsValidator:
        policy = SecretsPolicy.for_environment(Environment.DEVELOPMENT)
        return SecretsValidator(policy)

    def test_placeholder_in_dev_does_not_raise(
        self, dev_validator: SecretsValidator
    ) -> None:
        # allow_placeholders_in_dev=True → no ConfigurationError
        dev_validator.validate({"JWT_SECRET": "dev-secret"})

    def test_short_value_warns_but_no_raise(
        self, dev_validator: SecretsValidator, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Must not raise — non-strict mode only warns.
        dev_validator.validate({"JWT_SECRET": "short"})
        # The framework uses structlog which writes to stdout;
        # verify the warning event appeared in captured output.
        captured = capsys.readouterr()
        assert "secrets.validation.warning" in captured.out

    def test_valid_value_passes_silently(self, dev_validator: SecretsValidator) -> None:
        dev_validator.validate({"JWT_SECRET": "a" * 32})


# ---------------------------------------------------------------------------
# strict=True override in DEVELOPMENT
# ---------------------------------------------------------------------------


class TestStrictOverrideInDevelopment:
    def test_strict_true_overrides_dev_defaults(self) -> None:
        policy = SecretsPolicy(strict=True, allow_placeholders_in_dev=False)
        validator = SecretsValidator(policy)
        with pytest.raises(ConfigurationError):
            validator.validate({"JWT_SECRET": "change-me"})

    def test_strict_true_dev_with_allow_placeholders_still_enforces_length(
        self,
    ) -> None:
        # allow_placeholders_in_dev lets placeholder pass, but strict still
        # enforces minimum lengths for non-placeholder values.
        policy = SecretsPolicy(strict=True, allow_placeholders_in_dev=True)
        validator = SecretsValidator(policy)
        with pytest.raises(ConfigurationError, match="too short"):
            # "abc" is not a placeholder but is too short
            validator.validate({"JWT_SECRET": "abc"})


# ---------------------------------------------------------------------------
# Custom placeholder set
# ---------------------------------------------------------------------------


class TestCustomPlaceholderSet:
    def test_custom_placeholder_detected(self) -> None:
        policy = SecretsPolicy(
            strict=True,
            allow_placeholders_in_dev=False,
            placeholders=frozenset({"my-custom-placeholder"}),
        )
        validator = SecretsValidator(policy)
        with pytest.raises(ConfigurationError, match="placeholder"):
            validator.validate({"JWT_SECRET": "my-custom-placeholder"})

    def test_default_placeholder_not_detected_when_overridden(self) -> None:
        # Replace default set with empty — "change-me" should no longer be caught
        policy = SecretsPolicy(
            strict=True,
            allow_placeholders_in_dev=False,
            placeholders=frozenset(),
            min_lengths={},  # also disable length checks to isolate test
        )
        validator = SecretsValidator(policy)
        # "change-me" has no length constraint under empty min_lengths — passes
        validator.validate({"SOME_SECRET": "change-me"})


# ---------------------------------------------------------------------------
# Per-secret-name length override
# ---------------------------------------------------------------------------


class TestPerSecretNameLengthOverride:
    def test_custom_min_length_enforced(self) -> None:
        policy = SecretsPolicy(
            strict=True,
            allow_placeholders_in_dev=False,
            min_lengths={"my_app_token": 64},
        )
        validator = SecretsValidator(policy)
        with pytest.raises(ConfigurationError, match="too short"):
            validator.validate({"MY_APP_TOKEN": "a" * 32})  # 32 < 64

    def test_custom_min_length_passes_when_met(self) -> None:
        policy = SecretsPolicy(
            strict=True,
            allow_placeholders_in_dev=False,
            min_lengths={"my_app_token": 16},
        )
        validator = SecretsValidator(policy)
        validator.validate({"MY_APP_TOKEN": "a" * 16})


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_validator_satisfies_protocol(self) -> None:
        validator = SecretsValidator(SecretsPolicy())
        assert isinstance(validator, SecretsValidatorProtocol)


# ---------------------------------------------------------------------------
# SecretViolation value object
# ---------------------------------------------------------------------------


class TestSecretViolation:
    def test_frozen(self) -> None:
        v = SecretViolation(name="FOO", reason="bar")
        with pytest.raises((AttributeError, TypeError)):
            v.name = "OTHER"  # type: ignore[misc]

    def test_fields(self) -> None:
        v = SecretViolation(name="JWT_SECRET", reason="too short")
        assert v.name == "JWT_SECRET"
        assert v.reason == "too short"


# ---------------------------------------------------------------------------
# SecretsPolicy immutability (frozen dataclass)
# ---------------------------------------------------------------------------


class TestSecretsPolicyImmutability:
    def test_frozen(self) -> None:
        policy = SecretsPolicy()
        with pytest.raises((AttributeError, TypeError)):
            policy.strict = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Default constants sanity
# ---------------------------------------------------------------------------


class TestDefaultConstants:
    def test_default_placeholders_non_empty(self) -> None:
        assert len(DEFAULT_PLACEHOLDER_VALUES) > 0
        assert "" in DEFAULT_PLACEHOLDER_VALUES
        assert "change-me" in DEFAULT_PLACEHOLDER_VALUES

    def test_default_min_lengths_has_jwt(self) -> None:
        assert "jwt_secret" in DEFAULT_MIN_LENGTHS
        assert DEFAULT_MIN_LENGTHS["jwt_secret"] >= 32


# ---------------------------------------------------------------------------
# SecretStore-backed validation
# ---------------------------------------------------------------------------


class MockSecretStore:
    """Mock SecretStore for testing register_secrets_from_store."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets

    def get_secret(self, name: str) -> str:
        """Get a secret, raising SecretNotFoundError if not found."""
        from quadkit.contracts.security import SecretNotFoundError

        if name not in self._secrets:
            raise SecretNotFoundError(name)
        return self._secrets[name]

    def has_secret(self, name: str) -> bool:
        """Check if a secret exists."""
        return name in self._secrets

    def set_secret(self, name: str, value: str) -> None:
        """Set a secret."""
        self._secrets[name] = value

    def delete_secret(self, name: str) -> None:
        """Delete a secret."""
        self._secrets.pop(name, None)


class TestSecretsValidatorWithSecretStore:
    """Test SecretsValidator behavior when secrets come from a SecretStore."""

    def test_store_secret_valid_passes(self) -> None:
        """A valid secret from a store should pass validation."""
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        validator = SecretsValidator(policy)

        # Construct a dict as if pulled from a store
        store_secrets = {"NEXTAUTH_SECRET": "a" * 32}
        validator.validate(store_secrets)

    def test_store_secret_placeholder_raises_in_production(self) -> None:
        """A placeholder secret from a store should fail in production."""
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        validator = SecretsValidator(policy)

        store_secrets = {"NEXTAUTH_SECRET": "change-me"}
        with pytest.raises(ConfigurationError, match="placeholder"):
            validator.validate(store_secrets)

    def test_store_secret_missing_treated_as_empty(self) -> None:
        """A missing secret from a store is treated as empty string."""
        # This is the caller's responsibility to handle SecretNotFoundError
        # and pass empty string to validator, but test the validation behavior.
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        validator = SecretsValidator(policy)

        store_secrets = {"NEXTAUTH_SECRET": ""}
        with pytest.raises(ConfigurationError):
            validator.validate(store_secrets)

    def test_store_secret_short_raises_in_production(self) -> None:
        """A short secret from a store should fail in production."""
        policy = SecretsPolicy.for_environment(Environment.PRODUCTION)
        validator = SecretsValidator(policy)

        # JWT secrets have ≥32 char minimum
        store_secrets = {"JWT_SECRET": "short"}
        with pytest.raises(ConfigurationError, match="too short"):
            validator.validate(store_secrets)

    def test_store_secret_placeholder_allowed_in_dev(self) -> None:
        """A placeholder secret from a store is allowed in dev."""
        policy = SecretsPolicy.for_environment(Environment.DEVELOPMENT)
        validator = SecretsValidator(policy)

        store_secrets = {"NEXTAUTH_SECRET": "dev-secret"}
        # Should not raise
        validator.validate(store_secrets)
