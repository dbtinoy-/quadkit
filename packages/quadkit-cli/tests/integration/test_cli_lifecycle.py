"""Integration tests for quadkit-cli package."""

from __future__ import annotations

import pytest

from quadkit.cli.di.provider import CLIProvider


class TestCLIProviderIntegration:
    """Integration tests for CLIProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test CLIProvider initialization with default config."""
        provider = CLIProvider()
        assert provider.name == "cli"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = CLIProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = CLIProvider()
        assert provider.priority == ProviderPriority.APPLICATION


class TestCLIModuleIntegration:
    """Integration tests for CLIModule."""

    @pytest.mark.integration
    def test_cli_module_import(self):
        """Test CLIModule can be imported."""
        from quadkit.cli.module import CLIModule
        assert CLIModule is not None

    @pytest.mark.integration
    def test_cli_module_has_configure_method(self):
        """Test CLIModule has configure method."""
        from quadkit.cli.module import CLIModule
        assert hasattr(CLIModule, "configure")


class TestCLIContributorsIntegration:
    """Integration tests for CLI contributors."""

    @pytest.mark.integration
    def test_contributor_registry_import(self):
        """Test ContributorRegistry can be imported."""
        from quadkit.cli.contributors.registry import CliContributorRegistry
        assert CliContributorRegistry is not None


class TestCLIGeneratorsIntegration:
    """Integration tests for CLI generators."""

    @pytest.mark.integration
    def test_generator_registry_import(self):
        """Test GeneratorRegistry can be imported."""
        from quadkit.cli.registry.generator import GeneratorRegistry
        assert GeneratorRegistry is not None