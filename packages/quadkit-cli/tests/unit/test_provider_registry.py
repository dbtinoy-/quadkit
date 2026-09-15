"""Tests for ProviderRegistry and ProviderInstaller config merging.

Verifies that `quadkit add <provider>` (ProviderInstaller.add_provider_config)
merges YAML config sections without overwriting existing keys.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from quadkit.cli.registry.provider import ProviderInstaller, ProviderRegistry


class TestProviderInstallerConfigMerging:
    """Tests that add_provider_config() merges without overwriting."""

    def test_adds_new_keys_to_existing_config(self, tmp_path: Path) -> None:
        """New provider keys are merged into existing YAML config."""
        config_file = tmp_path / "application.yaml"
        config_file.write_text("app:\n  name: my-app\n")

        registry = ProviderRegistry.with_defaults()
        provider = registry.get("database")
        assert provider is not None

        result = ProviderInstaller.add_provider_config(
            provider, config_path=str(config_file)
        )
        assert result is True

        content = yaml.safe_load(config_file.read_text())
        # Original key preserved
        assert content["app"]["name"] == "my-app"
        # New database key was added
        assert "database" in content

    def test_does_not_overwrite_existing_keys(self, tmp_path: Path) -> None:
        """Existing config keys are NOT overwritten by add_provider_config."""
        config_file = tmp_path / "application.yaml"
        # Pre-configure a database section with custom value
        existing_config = {
            "database": {
                "url": "postgresql://my-custom-host:5432/my_db",
            }
        }
        config_file.write_text(yaml.dump(existing_config))

        registry = ProviderRegistry.with_defaults()
        provider = registry.get("database")
        assert provider is not None

        result = ProviderInstaller.add_provider_config(
            provider, config_path=str(config_file)
        )
        assert result is True

        content = yaml.safe_load(config_file.read_text())
        # Custom URL must not be overwritten by provider's default
        assert content["database"]["url"] == "postgresql://my-custom-host:5432/my_db"

    def test_returns_false_when_config_file_missing(self, tmp_path: Path) -> None:
        """add_provider_config() returns False if config file doesn't exist."""
        registry = ProviderRegistry.with_defaults()
        provider = registry.get("cache")
        assert provider is not None

        result = ProviderInstaller.add_provider_config(
            provider, config_path=str(tmp_path / "nonexistent.yaml")
        )
        assert result is False

    def test_creates_new_keys_on_empty_config(self, tmp_path: Path) -> None:
        """All provider keys are added when config is empty."""
        config_file = tmp_path / "application.yaml"
        config_file.write_text("{}\n")

        registry = ProviderRegistry.with_defaults()
        provider = registry.get("cache")
        assert provider is not None

        result = ProviderInstaller.add_provider_config(
            provider, config_path=str(config_file)
        )
        assert result is True

        content = yaml.safe_load(config_file.read_text()) or {}
        provider_info = provider.get_info()
        for key in provider_info.config:
            assert key in content

    def test_multiple_providers_merged_sequentially(self, tmp_path: Path) -> None:
        """Running add_provider_config multiple times accumulates all keys."""
        config_file = tmp_path / "application.yaml"
        config_file.write_text("{}\n")

        registry = ProviderRegistry.with_defaults()
        db_provider = registry.get("database")
        cache_provider = registry.get("cache")
        assert db_provider is not None
        assert cache_provider is not None

        ProviderInstaller.add_provider_config(
            db_provider, config_path=str(config_file)
        )
        ProviderInstaller.add_provider_config(
            cache_provider, config_path=str(config_file)
        )

        content = yaml.safe_load(config_file.read_text()) or {}
        # Both providers' top-level keys must be present
        db_keys = set(db_provider.get_info().config)
        cache_keys = set(cache_provider.get_info().config)
        for key in db_keys:
            assert key in content
        for key in cache_keys:
            assert key in content


class TestProviderRegistry:
    """Tests for ProviderRegistry registration and lookup."""

    def test_get_known_provider(self) -> None:
        """get() returns the provider for a known name."""
        reg = ProviderRegistry.with_defaults()
        provider = reg.get("database")
        assert provider is not None
        assert provider.get_info().name == "database"

    def test_get_unknown_provider_returns_none(self) -> None:
        """get() returns None for an unregistered name."""
        reg = ProviderRegistry.with_defaults()
        result = reg.get("does-not-exist")
        assert result is None

    def test_get_choices_includes_all_defaults(self) -> None:
        """get_choices() includes all default provider names."""
        reg = ProviderRegistry.with_defaults()
        choices = reg.get_choices()
        expected = {"database", "auth", "ai", "cache", "messaging", "events"}
        for name in expected:
            assert name in choices, f"'{name}' missing from get_choices()"

    def test_get_all_returns_copy(self) -> None:
        """get_all() returns a copy so mutation doesn't affect the registry."""
        reg = ProviderRegistry.with_defaults()
        all_providers = reg.get_all()
        count_before = len(all_providers)
        all_providers["fake"] = None  # type: ignore[assignment]
        # Registry should be unaffected
        assert len(reg.get_all()) == count_before
