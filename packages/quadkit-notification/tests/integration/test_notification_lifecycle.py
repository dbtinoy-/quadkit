"""Integration tests for quadkit-notification package."""

from __future__ import annotations

import pytest

from quadkit.notification.config import NotificationConfig
from quadkit.notification.di.provider import NotificationProvider


class TestNotificationProviderIntegration:
    """Integration tests for NotificationProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test NotificationProvider initialization with default config."""
        provider = NotificationProvider()
        assert provider.name == "notification"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test NotificationProvider initialization with custom config."""
        config = NotificationConfig()
        provider = NotificationProvider(config=config)
        assert provider.name == "notification"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = NotificationProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = NotificationProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestNotificationConfigIntegration:
    """Integration tests for NotificationConfig."""

    @pytest.mark.integration
    def test_notification_config_creation(self):
        """Test NotificationConfig can be created."""
        config = NotificationConfig()
        assert config is not None

    @pytest.mark.integration
    def test_notification_config_model_dump(self):
        """Test NotificationConfig model can be serialized."""
        config = NotificationConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestNotificationModuleIntegration:
    """Integration tests for NotificationModule."""

    @pytest.mark.integration
    def test_notification_module_import(self):
        """Test NotificationModule can be imported."""
        from quadkit.notification.module import NotificationModule
        assert NotificationModule is not None


class TestNotificationInboxIntegration:
    """Integration tests for notification inbox."""

    @pytest.mark.integration
    def test_inbox_service_import(self):
        """Test InboxService can be imported."""
        from quadkit.notification.inbox.service import InboxService
        assert InboxService is not None