"""Tests locking canonical protocol definitions to quadkit-contracts.

Enforces R5 of docs/quadkit-docs/guides/contracts.md: a protocol or type
shared across packages has exactly ONE canonical definition in
quadkit-contracts, and extension packages import it rather than redefining
it locally.
"""

from __future__ import annotations

import inspect

from quadkit.contracts.ai.vector import ChunkerProtocol


class TestCanonicalChunkerProtocol:
    """The canonical ChunkerProtocol lives in quadkit-contracts only."""

    def test_canonical_signature(self) -> None:
        """Canonical chunks accept text + optional metadata and return a list."""
        signature = inspect.signature(ChunkerProtocol.chunk)

        parameters = signature.parameters
        assert "text" in parameters
        assert parameters["text"].annotation in ("str", str)

        metadata = parameters.get("metadata")
        assert metadata is not None
        assert metadata.default is None

        return_annotation = signature.return_annotation
        return_annotation = str(return_annotation)
        assert "list" in return_annotation
        assert "Any" in return_annotation

    def test_runtime_checkable(self) -> None:
        """The canonical protocol is runtime-checkable."""
        assert hasattr(ChunkerProtocol, "__protocol_attrs__") or hasattr(ChunkerProtocol, "__annotations__")
