import os

import pytest
from quadkit.auth.config import (
    AuthConfig,
    AuthMiddlewareConfig,
    AuthRoleConfig,
    AuthUserConfig,
    JWTConfig,
    PasswordConfig,
    RBACConfig,
)
from quadkit.auth.constants import DEFAULT_EXCLUDED_PATHS


class TestAuthConfigDefaults:
    def test_default_enabled(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.enabled is True

    def test_default_name(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.name == "auth"

    def test_default_rbac(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert isinstance(config.rbac, RBACConfig)
        assert config.rbac.enabled is True

    def test_default_middleware(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert isinstance(config.middleware, AuthMiddlewareConfig)

    def test_default_password_config(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert isinstance(config.password, PasswordConfig)

    def test_default_users_empty(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.users == []

    def test_default_roles_empty(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.roles == {}

    def test_default_oauth2_providers_empty(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.oauth2_providers == {}

    def test_default_max_sessions_none(self) -> None:
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert config.max_sessions_per_user is None


class TestAuthConfigProductionSecurity:
    def test_rejects_default_secret_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                AuthConfig(secret_key="change-me", token={"secret_key": "change-me"})
            assert "CRITICAL SECURITY ERROR" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"

    def test_rejects_your_secret_key_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                AuthConfig(
                    secret_key="your-secret-key",
                    token={"secret_key": "your-secret-key"},
                )
            assert "CRITICAL SECURITY ERROR" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"

    def test_rejects_default_admin_password_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                AuthConfig(
                    secret_key="secure-key",
                    token={"secret_key": "secure-key", "required_audience": "my-service"},
                    admin_password="password",
                )
            assert "CRITICAL SECURITY ERROR" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"

    def test_accepts_secure_keys_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            config = AuthConfig(
                secret_key="secure-key",
                token={"secret_key": "secure-key", "required_audience": "my-service"},
            )
            assert config.secret_key == "secure-key"
        finally:
            os.environ["QK_ENV"] = "development"


class TestJWTConfigDefaults:
    def test_default_algorithm(self) -> None:
        config = JWTConfig(secret_key="test-key")
        assert config.algorithm == "HS256"

    def test_default_access_token_expire(self) -> None:
        config = JWTConfig(secret_key="test-key")
        assert config.access_token_expire.total_seconds == 30 * 60

    def test_default_key_rotation_grace_period(self) -> None:
        config = JWTConfig(secret_key="test-key")
        assert config.key_rotation_grace_period.total_seconds == 3600

    def test_default_audience_none(self) -> None:
        config = JWTConfig(secret_key="test-key")
        assert config.required_audience is None


class TestJWTConfigProductionSecurity:
    def test_rejects_default_secret_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                JWTConfig(secret_key="change-me")
            assert "CRITICAL SECURITY ERROR" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"

    def test_rejects_short_hs256_in_production(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                JWTConfig(secret_key="short-key", algorithm="HS256")
            assert "SECURITY ERROR" in str(excinfo.value)
            assert "at least 32 bytes" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"


class TestRBACConfigDefaults:
    def test_default_enabled(self) -> None:
        config = RBACConfig()
        assert config.enabled is True

    def test_default_superuser_bypass(self) -> None:
        config = RBACConfig()
        assert config.superuser_bypass is True

    def test_default_role(self) -> None:
        config = RBACConfig()
        assert config.default_role == "viewer"

    def test_default_cache_permissions(self) -> None:
        config = RBACConfig()
        assert config.cache_permissions is True

    def test_default_permission_cache_ttl(self) -> None:
        config = RBACConfig()
        assert config.permission_cache_ttl == 300


class TestAuthMiddlewareConfigDefaults:
    def test_default_exclude_paths(self) -> None:
        # The default is the routes this package serves itself plus the static
        # docs and health endpoints, so login is reachable without a
        # credential. Throttling is not part of this list — the middleware
        # applies the rate limiter to `/auth/login` and `/auth/register`
        # whether or not they are excluded here.
        config = AuthMiddlewareConfig()
        assert config.exclude_paths == list(DEFAULT_EXCLUDED_PATHS)

    def test_default_backend(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.backend == "session"

    def test_default_header_name(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.header_name == "Authorization"

    def test_default_scheme(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.scheme == "Bearer"

    def test_default_roles_required(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.roles_required == []

    def test_default_permissions_required(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.permissions_required == []

    def test_default_optional_auth(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.optional_auth is False

    def test_default_login_url_none(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.login_url is None

    def test_default_exclude_prefixes(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.exclude_prefixes == []

    def test_default_login_rate_limit(self) -> None:
        config = AuthMiddlewareConfig()
        assert config.login_rate_limit == "5/minute"


class TestAuthUserConfigDefaults:
    def test_default_username_none(self) -> None:
        config = AuthUserConfig(name="test", email="test@example.com")
        assert config.username is None

    def test_default_password_none(self) -> None:
        config = AuthUserConfig(name="test", email="test@example.com")
        assert config.password is None

    def test_default_password_hash_none(self) -> None:
        config = AuthUserConfig(name="test", email="test@example.com")
        assert config.password_hash is None

    def test_default_roles_empty(self) -> None:
        config = AuthUserConfig(name="test", email="test@example.com")
        assert config.roles == []

    def test_default_is_active_true(self) -> None:
        config = AuthUserConfig(name="test", email="test@example.com")
        assert config.is_active is True


class TestAuthRoleConfigDefaults:
    def test_default_description_empty(self) -> None:
        config = AuthRoleConfig(name="test")
        assert config.description == ""

    def test_default_permissions_empty(self) -> None:
        config = AuthRoleConfig(name="test")
        assert config.permissions == []

    def test_default_inherits_empty(self) -> None:
        config = AuthRoleConfig(name="test")
        assert config.inherits == []


class TestJWTSecretQuality:
    def test_hs384_requires_long_secret(self) -> None:
        os.environ["QK_ENV"] = "production"
        try:
            with pytest.raises(ValueError) as excinfo:
                AuthConfig(
                    secret_key="secure-key",
                    token=JWTConfig(secret_key="short", algorithm="HS384"),
                )
            assert "SECURITY ERROR" in str(excinfo.value)
        finally:
            os.environ["QK_ENV"] = "development"


class TestJWTSecretMasking:
    def test_jwt_secret_key_is_masked_from_plain_string(self) -> None:
        os.environ["QK_ENV"] = "development"
        try:
            cfg = JWTConfig(secret_key="x" * 64)
            secret_attr = getattr(cfg, "secret_key")
            assert hasattr(secret_attr, "get_secret_value")
            assert "x" * 64 not in repr(secret_attr)
            assert secret_attr.get_secret_value() == "x" * 64
        finally:
            os.environ["QK_ENV"] = "development"
