"""Application adapter around Quadkit's BlobStoreProtocol."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from artifact_vault.config import ArtifactVaultConfig
from quadkit.contracts import BlobStoreProtocol
from quadkit.contracts.infra.storage import FileInfo, UploadOptions
from quadkit.storage.exceptions import StorageUnsupportedOperationError


class ArtifactVaultService:
    """Provide an intentionally small artifact vault for browser exploration."""

    def __init__(self, store: BlobStoreProtocol, config: ArtifactVaultConfig) -> None:
        self._store = store
        self._config = config

    async def seed(self) -> None:
        """Put one deterministic artifact in the memory backend on boot."""
        if self._config.seed_welcome_artifact and not await self._store.exists(
            "docs/welcome.txt"
        ):
            await self._store.upload(
                "docs/welcome.txt",
                "Welcome to Artifact Vault. Upload, inspect, preview, and delete an artifact.",
                UploadOptions(
                    content_type="text/plain",
                    metadata={"owner": "quadkit", "kind": "guide"},
                ),
            )

    async def list(self, prefix: str = "") -> list[dict[str, Any]]:
        """List all artifacts matching an optional path prefix."""
        items: list[dict[str, Any]] = []
        async for info in self._store.list(prefix):
            items.append(self._info(info))
        return items

    async def upload(
        self, name: str, content: str, content_type: str, owner: str
    ) -> dict[str, Any]:
        """Upload a new artifact with validation and size limits."""
        path = self._safe_path(name)
        if not content:
            raise ValueError("Artifact content is required")
        if len(content.encode("utf-8")) > 1_000_000:
            raise ValueError("Artifact is limited to 1 MB in this demo")
        info = await self._store.upload(
            path,
            content,
            UploadOptions(
                content_type=content_type or "text/plain",
                metadata={
                    "owner": owner.strip() or "demo-user",
                    "kind": "browser-upload",
                },
            ),
        )
        return self._info(info)

    async def content(self, name: str) -> dict[str, Any]:
        """Download and return the content of an artifact."""
        path = self._safe_path(name)
        info = await self._store.info(path)
        raw = await self._store.download(path)
        return {
            "path": path,
            "content": raw.decode("utf-8", errors="replace"),
            "metadata": self._info(info),
        }

    async def delete(self, name: str) -> None:
        """Delete an artifact from the blob store."""
        await self._store.delete(self._safe_path(name))

    async def access(self, name: str) -> dict[str, Any]:
        """Show the driver's URL capabilities honestly in the console."""
        path = self._safe_path(name)
        public_url = await self._store.get_url(path)
        try:
            signed_url = await self._store.get_presigned_url(
                path, timedelta(minutes=10)
            )
        except StorageUnsupportedOperationError as exc:
            return {
                "path": path,
                "public_url": public_url,
                "signed_access": False,
                "message": str(exc),
            }
        return {
            "path": path,
            "public_url": public_url,
            "signed_access": True,
            "signed_url": signed_url,
        }

    async def health(self) -> dict[str, Any]:
        """Check and return the blob store health status."""
        result = await self._store.health_check()
        return {"status": result.status.value, "details": result.details or {}}

    @staticmethod
    def _safe_path(name: str) -> str:
        path = name.strip().lstrip("/")
        if not path or path in {".", ".."} or ".." in path.split("/"):
            raise ValueError("Use a relative artifact name without '..'")
        return path

    @staticmethod
    def _info(info: FileInfo) -> dict[str, Any]:
        return {
            "path": info.path,
            "size": info.size,
            "content_type": info.content_type,
            "etag": info.etag,
            "metadata": info.metadata or {},
            "last_modified": info.last_modified.isoformat(),
        }


__all__ = ["ArtifactVaultService"]
