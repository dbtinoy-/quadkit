"""Content-addressed checkpoint primitives for workflow sagas.

Provides the structured key, entry, and store protocol needed for
content-addressed checkpointing where stage outputs are keyed by
``sha256(stage_id || tenant_id || inputs)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json as _stdlib_json
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ContentCheckpointEntry",
    "ContentCheckpointKey",
    "ContentCheckpointStoreProtocol",
]


def _canonical_json_bytes(obj: Any) -> bytes:
    """Serialize *obj* to canonical JSON bytes for content addressing."""

    def _default(value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    return _stdlib_json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


@dataclass(frozen=True)
class ContentCheckpointKey:
    """Structured key for content-addressed stage outputs.

    The string form is ``f"{stage_id}|{tenant_id or '_global'}|{input_hash.hex()}|{config_hash.hex()}"``,
    stable across processes and deploys.
    """

    stage_id: str
    tenant_id: str | None
    input_hash: bytes
    config_hash: bytes

    def as_str(self) -> str:
        """Return the string form for use as a storage key."""
        tenant = self.tenant_id or "_global"
        return (
            f"{self.stage_id}|{tenant}|{self.input_hash.hex()}|{self.config_hash.hex()}"
        )

    @classmethod
    def compute(
        cls,
        stage_id: str,
        tenant_id: str | None,
        inputs: dict[str, Any],
        stage_handler_version: str,
        config_affecting_output: dict[str, Any],
    ) -> ContentCheckpointKey:
        """Compute a content-addressed key from stage parameters."""
        input_bytes = _canonical_json_bytes(inputs)
        config_bytes = _canonical_json_bytes(
            {
                "handler_version": stage_handler_version,
                "config": config_affecting_output,
            }
        )
        return cls(
            stage_id=stage_id,
            tenant_id=tenant_id,
            input_hash=hashlib.sha256(input_bytes).digest(),
            config_hash=hashlib.sha256(config_bytes).digest(),
        )


@dataclass(frozen=True)
class ContentCheckpointEntry:
    """A stored checkpoint entry for a content-addressed stage output.

    When the output exceeds the inline threshold, ``output`` is ``None`` and
    ``output_blob_ref`` holds the ``quadkit-storage`` blob reference.
    """

    output: Any
    output_blob_ref: str | None
    completed_at: datetime
    stage_handler_version: str
    output_size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ContentCheckpointStoreProtocol(Protocol):
    """Persistence contract for content-addressed checkpoint entries."""

    async def get(self, key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
        """Retrieve a cached checkpoint entry, or ``None``."""

    async def set(
        self, key: ContentCheckpointKey, entry: ContentCheckpointEntry
    ) -> None:
        """Persist a checkpoint entry."""

    async def evict(self, key: ContentCheckpointKey) -> None:
        """Remove a checkpoint entry."""

    async def list_by_stage(
        self,
        stage_id: str,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[ContentCheckpointKey]:
        """List checkpoint keys for a given stage, optionally filtered by tenant."""
