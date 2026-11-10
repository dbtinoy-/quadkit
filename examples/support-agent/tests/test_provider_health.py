"""Provider readiness must reflect lifecycle, not unconditional success."""

from __future__ import annotations

from support_agent.config import SupportAgentConfig
from support_agent.di.provider import AgentSupportProvider

from quadkit.contracts.core.health import HealthStatus


async def test_health_before_boot_uses_typed_config_and_is_not_ready() -> None:
    provider = AgentSupportProvider()
    provider.config = SupportAgentConfig(service_name="audit example")
    result = await provider.health_check()
    assert result.status is HealthStatus.UNHEALTHY
    assert result.message == "audit example provider not ready"


async def test_health_after_real_boot_and_shutdown() -> None:
    from support_agent.app import create_app

    application = create_app()
    await application.start()
    try:
        provider = next(
            p for p in application.providers if isinstance(p, AgentSupportProvider)
        )
        result = await provider.health_check()
        assert result.status is HealthStatus.HEALTHY
        assert result.message.endswith(" provider ready")
    finally:
        await application.stop()
    assert provider._support is None
    assert (await provider.health_check()).status is HealthStatus.UNHEALTHY


async def test_health_without_config_is_not_ready() -> None:
    provider = AgentSupportProvider()
    result = await provider.health_check()
    assert result.status is HealthStatus.UNHEALTHY
    assert result.details is not None
    assert result.details["ready"] is False
