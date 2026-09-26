"""Tests for auth MFA provider."""

import pytest

from quadkit.auth.di.sub_providers.mfa_provider import MFAProvider
from quadkit.contracts.core import HealthStatus


class TestMFAProvider:
    def test_mfa_provider_creation(self) -> None:
        provider = MFAProvider()
        assert provider.name == "mfa"

    def test_mfa_provider_priority(self) -> None:
        from quadkit.contracts.core import ProviderPriority

        provider = MFAProvider()
        assert provider.priority == ProviderPriority.SECURITY

    @pytest.mark.asyncio
    async def test_mfa_provider_boot(self) -> None:
        provider = MFAProvider()
        await provider.boot(None)
        # Just verify it doesn't raise

    @pytest.mark.asyncio
    async def test_mfa_provider_shutdown(self) -> None:
        provider = MFAProvider()
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_mfa_provider_health_check(self) -> None:
        provider = MFAProvider()
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "mfa"
        assert "totp_digits" in result.details
        assert "backup_count" in result.details
