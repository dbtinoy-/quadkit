from unittest.mock import AsyncMock

import pytest

from quadkit.app.base import Application, AppState
from quadkit.config import QuadkitConfig
from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)


@pytest.mark.asyncio
async def test_application_interface_reduced():
    """`Application` should no longer expose helpers that encourage service locator."""
    app = Application()

    # the methods were removed as part of MAJOR-4.3
    assert not hasattr(app, "invoke")
    assert not hasattr(app, "get_config")
    # properties that remain
    assert app.container is not None
    assert isinstance(app.config, QuadkitConfig)


@pytest.mark.asyncio
async def test_invoker_resolves_and_calls():
    """DI injection for entry-point functions goes through ``Invoker``, not ``container.call``."""
    from quadkit.app.invoker import Invoker

    app = Application()

    # register a simple singleton so resolution is deterministic
    cfg = QuadkitConfig()
    app.container.singleton(QuadkitConfig, cfg)

    async def helper(config: QuadkitConfig) -> bool:
        # return whether the injected config is the same instance
        return config is cfg

    # Invoker is pre-registered in __init__ — resolvable without booting
    invoker = await app.container.resolve(Invoker)
    result = await invoker.invoke(helper)
    assert result is True


@pytest.mark.asyncio
async def test_application_probe_methods_delegate_to_orchestrator() -> None:
    """Application probe methods should delegate to orchestrator probes."""
    app = Application()
    app._state = AppState.RUNNING

    app._orchestrator.run_liveness = AsyncMock(
        return_value=AggregateHealthResult(
            components=[
                HealthCheckResult(
                    component="live",
                    status=HealthStatus.HEALTHY,
                    category=HealthCheckCategory.LIVENESS,
                ),
            ],
        ),
    )
    app._orchestrator.run_readiness = AsyncMock(
        return_value=AggregateHealthResult(
            components=[
                HealthCheckResult(
                    component="ready",
                    status=HealthStatus.DEGRADED,
                    category=HealthCheckCategory.READINESS,
                ),
            ],
        ),
    )
    app._orchestrator.run_startup = AsyncMock(
        return_value=AggregateHealthResult(
            components=[
                HealthCheckResult(
                    component="startup",
                    status=HealthStatus.HEALTHY,
                    category=HealthCheckCategory.STARTUP,
                ),
            ],
        ),
    )

    liveness = await app.liveness()
    readiness = await app.readiness()
    startup = await app.startup_check()

    assert liveness.components[0].category == HealthCheckCategory.LIVENESS
    assert readiness.components[0].category == HealthCheckCategory.READINESS
    assert startup.components[0].category == HealthCheckCategory.STARTUP

    app._orchestrator.run_liveness.assert_awaited_once_with(5.0)
    app._orchestrator.run_readiness.assert_awaited_once_with(5.0)
    app._orchestrator.run_startup.assert_awaited_once_with(5.0)


@pytest.mark.asyncio
async def test_application_probe_methods_return_unhealthy_when_not_running() -> None:
    """Application probe methods should fail closed when the app is not running."""
    app = Application()

    result = await app.liveness()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.components[0].message == "Application is created"
    assert result.components[0].category == HealthCheckCategory.LIVENESS


# ---------------------------------------------------------------------------
# register_secrets_from_store tests
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


class TestApplicationSecretsFromStore:
    """Test Application.register_secrets_from_store."""

    def test_register_secrets_from_store_signature_exists(self) -> None:
        """Application should have register_secrets_from_store method."""
        app = Application()
        assert hasattr(app, "register_secrets_from_store")
        assert callable(app.register_secrets_from_store)

    def test_register_secrets_from_store_stores_registration(self) -> None:
        """Registering secrets from store should store the registration."""
        app = Application()
        store = MockSecretStore({"JWT_SECRET": "a" * 32})

        app.register_secrets_from_store(store, ["JWT_SECRET"])

        # Internal state should track the registration
        assert len(app._secrets_from_stores) == 1
        registered_store, registered_names = app._secrets_from_stores[0]
        assert registered_store is store
        assert registered_names == ["JWT_SECRET"]

    def test_register_secrets_from_store_multiple_names(self) -> None:
        """Should handle multiple secret names from one store."""
        app = Application()
        store = MockSecretStore(
            {
                "JWT_SECRET": "a" * 32,
                "OAUTH_SECRET": "b" * 16,
            }
        )

        app.register_secrets_from_store(
            store,
            ["JWT_SECRET", "OAUTH_SECRET"],
        )

        assert len(app._secrets_from_stores) == 1
        _, names = app._secrets_from_stores[0]
        assert names == ["JWT_SECRET", "OAUTH_SECRET"]

    def test_register_secrets_from_store_multiple_stores(self) -> None:
        """Should handle multiple separate store registrations."""
        app = Application()
        store1 = MockSecretStore({"JWT_SECRET": "a" * 32})
        store2 = MockSecretStore({"DB_PASSWORD": "b" * 16})

        app.register_secrets_from_store(store1, ["JWT_SECRET"])
        app.register_secrets_from_store(store2, ["DB_PASSWORD"])

        assert len(app._secrets_from_stores) == 2

    def test_register_secrets_from_store_with_policy(self) -> None:
        """register_secrets_from_store should accept optional policy."""
        from quadkit.config.secrets import SecretsPolicy

        app = Application()
        store = MockSecretStore({"JWT_SECRET": "a" * 32})
        policy = SecretsPolicy(strict=False)

        # Should not raise
        app.register_secrets_from_store(
            store,
            ["JWT_SECRET"],
            policy=policy,
        )

        assert app._secrets_policy is policy

    @pytest.mark.asyncio
    async def test_register_secrets_from_store_validation_passes(self) -> None:
        """Valid secrets from store should pass validation on start."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict({"env": Environment.PRODUCTION})
        store = MockSecretStore({"JWT_SECRET": "a" * 32})

        # Register secrets before boot
        app = Application(config=config)
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        # Should not raise
        await app.start()
        try:
            pass  # Just needed to complete boot
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_register_secrets_from_store_validation_fails_on_missing(
        self,
    ) -> None:
        """Missing secret from store should fail validation in production."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment
        from quadkit.contracts.exceptions import ConfigurationError

        config = QuadkitConfig.from_dict({"env": Environment.PRODUCTION})
        store = MockSecretStore({})  # Empty store

        app = Application(config=config)
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        with pytest.raises(ConfigurationError):
            await app.start()

    @pytest.mark.asyncio
    async def test_register_secrets_from_store_validation_warns_on_missing_in_dev(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Missing secret from store should warn but not fail in dev."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict({"env": Environment.DEVELOPMENT})
        store = MockSecretStore({})  # Empty store

        app = Application(config=config)
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        # Should not raise in dev (non-strict)
        await app.start()
        try:
            captured = capsys.readouterr()
            assert "secrets.validation.warning" in captured.out
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_mixed_literal_and_store_secrets(self) -> None:
        """Should handle both literal and store-sourced secrets together."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment

        config = QuadkitConfig.from_dict({"env": Environment.PRODUCTION})
        store = MockSecretStore({"JWT_SECRET": "a" * 32})

        app = Application(config=config)
        app.register_secrets({"OAUTH_SECRET": "b" * 16})
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        # Both should validate
        await app.start()
        try:
            pass
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_register_secrets_from_store_placeholder_fails_in_production(
        self,
    ) -> None:
        """Placeholder value from store should fail in production."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment
        from quadkit.contracts.exceptions import ConfigurationError

        config = QuadkitConfig.from_dict({"env": Environment.PRODUCTION})
        store = MockSecretStore({"JWT_SECRET": "change-me"})

        app = Application(config=config)
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        with pytest.raises(ConfigurationError, match="placeholder"):
            await app.start()

    @pytest.mark.asyncio
    async def test_register_secrets_from_store_short_value_fails_in_production(
        self,
    ) -> None:
        """Short value from store should fail in production."""
        from quadkit.config import QuadkitConfig
        from quadkit.contracts.core.config import Environment
        from quadkit.contracts.exceptions import ConfigurationError

        config = QuadkitConfig.from_dict({"env": Environment.PRODUCTION})
        store = MockSecretStore({"JWT_SECRET": "short"})

        app = Application(config=config)
        app.register_secrets_from_store(store, ["JWT_SECRET"])

        with pytest.raises(ConfigurationError, match="too short"):
            await app.start()
