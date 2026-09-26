"""Tests for storage models."""

import pytest

from quadkit.contracts.infra.storage import UploadOptions


class TestUploadOptions:
    """Tests for UploadOptions dataclass."""

    def test_default_values(self) -> None:
        """Test default UploadOptions values."""
        opts = UploadOptions()
        assert opts.content_type is None
        assert opts.public is False
        assert opts.metadata is None
        assert opts.cache_control is None

    def test_custom_values(self) -> None:
        """Test custom UploadOptions values."""
        opts = UploadOptions(
            content_type="image/png",
            public=True,
            metadata={"key": "value"},
            cache_control="max-age=3600",
        )
        assert opts.content_type == "image/png"
        assert opts.public is True
        assert opts.metadata == {"key": "value"}
        assert opts.cache_control == "max-age=3600"

    def test_metadata_normalization(self) -> None:
        """Test metadata keys are normalized to lowercase."""
        opts = UploadOptions(metadata={"KEY": "value1", "AnotherKey": "value2"})
        assert "key" in opts.metadata
        assert "anotherkey" in opts.metadata

    def test_metadata_case_insensitive(self) -> None:
        """Test metadata is case-insensitive after normalization."""
        opts = UploadOptions(metadata={"KEY": "value"})
        assert "key" in opts.metadata
        assert opts.metadata["key"] == "value"

    def test_public_option(self) -> None:
        """Test public option."""
        public_opts = UploadOptions(public=True)
        private_opts = UploadOptions(public=False)
        assert public_opts.public is True
        assert private_opts.public is False

    def test_types_exported(self) -> None:
        """Test that models are re-exported from the package root."""
        from quadkit.contracts.infra.storage import UploadOptions as ContractOptions
        from quadkit.storage import UploadOptions

        assert UploadOptions is ContractOptions
