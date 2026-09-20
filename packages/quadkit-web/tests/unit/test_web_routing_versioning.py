"""Tests for web routing versioning types."""

import pytest

from quadkit.web.routing.versioning import VersioningConfig, VersioningStrategy


class TestVersioningStrategy:
    """Tests for VersioningStrategy enum."""

    def test_versioning_strategy_values(self) -> None:
        """Test VersioningStrategy enum values."""
        assert VersioningStrategy.URI.value == "uri"
        assert VersioningStrategy.HEADER.value == "header"
        assert VersioningStrategy.MEDIA_TYPE.value == "media_type"
        assert VersioningStrategy.QUERY.value == "query"

    def test_versioning_strategy_members(self) -> None:
        """Test VersioningStrategy has expected members."""
        members = list(VersioningStrategy)
        assert len(members) == 4


class TestVersioningConfig:
    """Tests for VersioningConfig dataclass."""

    def test_versioning_config_defaults(self) -> None:
        """Test VersioningConfig default values."""
        config = VersioningConfig()
        assert config.strategy == VersioningStrategy.URI
        assert config.header_name == "X-API-Version"
        assert config.query_param == "api_version"
        assert config.default_version == "1"
        assert config.uri_prefix == "v"

    def test_versioning_config_with_values(self) -> None:
        """Test VersioningConfig with values."""
        config = VersioningConfig(
            strategy=VersioningStrategy.URI,
            header_name="X-Version",
            query_param="v",
            default_version="2",
            uri_prefix="api/v",
            media_type_prefix="application/vnd.myapi",
        )
        assert config.strategy == VersioningStrategy.URI
        assert config.header_name == "X-Version"
        assert config.query_param == "v"
        assert config.default_version == "2"
        assert config.uri_prefix == "api/v"
