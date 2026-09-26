"""Unit tests for storage driver protocols."""

import pytest
from quadkit.storage.backends.protocols import StreamingBodyProtocol, _S3ClientProtocol


class TestStorageProtocols:
    """Tests for storage driver protocols."""

    def test_streaming_body_protocol_importable(self):
        """Ensure StreamingBodyProtocol can be imported."""
        assert StreamingBodyProtocol is not None

    def test_s3_client_protocol_importable(self):
        """Ensure _S3ClientProtocol can be imported."""
        assert _S3ClientProtocol is not None

    def test_streaming_body_protocol_is_protocol(self):
        """Ensure StreamingBodyProtocol is a Protocol."""
        from typing import Protocol
        assert issubclass(StreamingBodyProtocol, Protocol)

    def test_s3_client_protocol_is_protocol(self):
        """Ensure _S3ClientProtocol is a Protocol."""
        from typing import Protocol
        assert issubclass(_S3ClientProtocol, Protocol)

    def test_streaming_body_protocol_runtime_checkable(self):
        """Ensure StreamingBodyProtocol is runtime_checkable."""
        assert hasattr(StreamingBodyProtocol, "_is_protocol")
        assert getattr(StreamingBodyProtocol, "_is_protocol", False) is not False
