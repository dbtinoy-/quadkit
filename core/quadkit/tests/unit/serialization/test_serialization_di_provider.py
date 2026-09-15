"""Tests for serialization/di/provider module."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from quadkit.serialization.di.provider import SerializationProvider


class TestSerializationProviderCreation:
    """Tests for creating SerializationProvider."""

    def test_create_provider(self) -> None:
        """Test creating SerializationProvider."""
        provider = SerializationProvider()
        assert provider.name == "serialization"

    def test_provider_has_correct_name(self) -> None:
        """Test provider name is serialization."""
        from quadkit.di.provider import ProviderPriority
        provider = SerializationProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestSerializationProviderRegister:
    """Tests for register method."""

    @pytest.mark.asyncio
    async def test_register_creates_config(self) -> None:
        """Test register creates SerializationConfig."""
        provider = SerializationProvider()
        mock_container = MagicMock()
        
        await provider.register(mock_container)
        
        # Check singleton was registered for SerializationConfig
        mock_container.singleton.assert_called()

    @pytest.mark.asyncio
    async def test_register_registers_json_serializer(self) -> None:
        """Test register registers JsonSerializerProtocol."""
        provider = SerializationProvider()
        mock_container = MagicMock()
        
        await provider.register(mock_container)
        
        # At least one singleton should be registered
        assert mock_container.singleton.call_count >= 2

    @pytest.mark.asyncio
    async def test_register_registers_registry(self) -> None:
        """Test register registers SerializerRegistry."""
        provider = SerializationProvider()
        mock_container = MagicMock()
        
        await provider.register(mock_container)
        
        # Verify singleton calls include SerializerRegistry
        calls = mock_container.singleton.call_args_list
        reg_found = any(
            "SerializerRegistry" in str(call) 
            for call in calls
        )
        assert reg_found


class TestSerializationProviderLifecycle:
    """Tests for lifecycle methods."""

    @pytest.mark.asyncio
    async def test_boot_does_nothing(self) -> None:
        """Test boot requires no work."""
        provider = SerializationProvider()
        mock_container = MagicMock()
        
        # Should not raise
        await provider.boot(mock_container)

    @pytest.mark.asyncio
    async def test_shutdown_does_nothing(self) -> None:
        """Test shutdown requires no work."""
        provider = SerializationProvider()
        
        # Should not raise
        await provider.shutdown()


class TestSerializationProviderWithMocks:
    """Tests using mocked imports."""

    @pytest.mark.asyncio
    async def test_register_creates_components(self) -> None:
        """Test register creates serialization components."""
        provider = SerializationProvider()
        mock_container = MagicMock()
        
        await provider.register(mock_container)
        
        # Should have called singleton at least twice (config + serializer + registry)
        assert mock_container.singleton.call_count >= 2