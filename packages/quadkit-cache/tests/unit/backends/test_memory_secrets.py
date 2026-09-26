"""Tests for memory secrets store."""

import pytest

from quadkit.cache.backends.memory_secrets import MemorySecretStore


class TestMemorySecretStore:
    """Tests for MemorySecretStore."""

    @pytest.fixture
    def store(self):
        return MemorySecretStore()

    @pytest.mark.asyncio
    async def test_get_secret_exists(self, store):
        """Should get existing secret."""
        await store.set_secret("api-key", "secret123")
        result = await store.get_secret("api-key")
        assert result == "secret123"

    @pytest.mark.asyncio
    async def test_get_secret_nonexistent(self, store):
        """Should return None for nonexistent secret."""
        result = await store.get_secret("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_secret(self, store):
        """Should set a secret."""
        await store.set_secret("new-secret", "secret-value")
        result = await store.get_secret("new-secret")
        assert result == "secret-value"

    @pytest.mark.asyncio
    async def test_set_secret_overwrite(self, store):
        """Should overwrite existing secret."""
        await store.set_secret("api-key", "value1")
        await store.set_secret("api-key", "value2")
        result = await store.get_secret("api-key")
        assert result == "value2"

    @pytest.mark.asyncio
    async def test_delete_secret(self, store):
        """Should delete a secret."""
        await store.set_secret("api-key", "secret")
        await store.delete_secret("api-key")
        result = await store.get_secret("api-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_secret(self, store):
        """Should not error when deleting nonexistent secret."""
        await store.delete_secret("nonexistent")

    @pytest.mark.asyncio
    async def test_list_secrets_all(self, store):
        """Should list all secrets."""
        await store.set_secret("key1", "value1")
        await store.set_secret("key2", "value2")
        
        result = await store.list_secrets()
        
        assert len(result) == 2
        assert "key1" in result
        assert "key2" in result

    @pytest.mark.asyncio
    async def test_list_secrets_with_prefix(self, store):
        """Should list secrets with prefix."""
        await store.set_secret("api-key1", "value1")
        await store.set_secret("api-key2", "value2")
        await store.set_secret("db-password", "value3")
        
        result = await store.list_secrets(prefix="api-")
        
        assert len(result) == 2
        assert "api-key1" in result
        assert "api-key2" in result
        assert "db-password" not in result

    @pytest.mark.asyncio
    async def test_list_secrets_empty(self, store):
        """Should return empty list when no secrets."""
        result = await store.list_secrets()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_secrets_no_matching_prefix(self, store):
        """Should return empty list when no matching prefix."""
        await store.set_secret("key1", "value1")
        
        result = await store.list_secrets(prefix="nonexistent")
        
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check(self, store):
        """Should return healthy status."""
        await store.set_secret("test", "value")
        
        result = await store.health_check()
        
        assert result.status.value == "healthy"
        assert result.component == "memory-secrets"
        assert result.details["secrets_count"] == 1


class TestMemorySecretStoreWithInitialSecrets:
    """Tests for MemorySecretStore with initial secrets."""

    @pytest.mark.asyncio
    async def test_with_initial_secrets(self):
        """Should initialize with provided secrets."""
        secrets = {"api-key": "secret123", "db-password": "dbpass"}
        store = MemorySecretStore(secrets=secrets)
        
        assert await store.get_secret("api-key") == "secret123"
        assert await store.get_secret("db-password") == "dbpass"

    @pytest.mark.asyncio
    async def test_with_empty_dict(self):
        """Should handle empty dict."""
        store = MemorySecretStore(secrets={})
        
        result = await store.list_secrets()
        assert result == []
