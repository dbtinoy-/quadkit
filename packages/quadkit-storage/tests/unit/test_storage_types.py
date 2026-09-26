"""Tests for storage types module."""

import pytest
from quadkit.contracts.infra.storage import UploadOptions


class TestUploadOptions:
    """Tests for UploadOptions dataclass."""

    def test_default_values(self):
        """Should have correct default values."""
        options = UploadOptions()
        
        assert options.content_type is None
        assert options.public is False
        assert options.metadata is None
        assert options.cache_control is None

    def test_with_content_type(self):
        """Should accept content_type."""
        options = UploadOptions(content_type="image/png")
        
        assert options.content_type == "image/png"
        assert options.public is False

    def test_with_public(self):
        """Should accept public flag."""
        options = UploadOptions(public=True)
        
        assert options.public is True
        assert options.content_type is None

    def test_with_metadata(self):
        """Should accept metadata dict."""
        options = UploadOptions(metadata={"author": "test"})
        
        assert options.metadata == {"author": "test"}

    def test_metadata_keys_normalized_to_lowercase(self):
        """Should normalize metadata keys to lowercase."""
        options = UploadOptions(metadata={"Author": "Test", "VERSION": "1.0"})
        
        assert "author" in options.metadata
        assert "version" in options.metadata
        assert options.metadata["author"] == "Test"
        assert options.metadata["version"] == "1.0"

    def test_metadata_none_remains_none(self):
        """Should handle None metadata."""
        options = UploadOptions(metadata=None)
        
        assert options.metadata is None

    def test_all_options_together(self):
        """Should accept all options at once."""
        options = UploadOptions(
            content_type="application/json",
            public=True,
            metadata={"key": "value"},
            cache_control="max-age=3600",
        )
        
        assert options.content_type == "application/json"
        assert options.public is True
        assert options.metadata == {"key": "value"}
        assert options.cache_control == "max-age=3600"

    def test_dataclass_repr(self):
        """Should have a useful repr."""
        options = UploadOptions(content_type="text/plain")
        
        repr_str = repr(options)
        assert "UploadOptions" in repr_str
        assert "text/plain" in repr_str
