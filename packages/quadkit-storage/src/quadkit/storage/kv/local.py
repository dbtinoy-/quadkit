"""Local file storage implementation for Quadkit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Any

import aiofiles

from quadkit import serialization as json
from quadkit.contracts.infra.storage import StorageBackendProtocol, StorageType
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts import HealthCheckResult

logger = get_logger(__name__)


class LocalStorage(StorageBackendProtocol):
    """Local file-based storage implementation with atomic writes."""

    def __init__(
        self,
        base_path: str | Path,
        file_extension: str = ".json",
        pretty_print: bool = False,
    ):
        self.base_path = Path(base_path)
        self.file_extension = file_extension
        self.pretty_print = pretty_print
        self._connected = False

    @property
    def storage_type(self) -> StorageType:
        return StorageType.FILE

    async def connect(self) -> None:
        """Ensure base path exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def _get_ns_dir(self, namespace: str | None) -> Path:
        """Map a namespace to a safe directory inside base_path.

        Applies the same charset filter the key uses; ``None``/empty and
        namespaces that filter down to a path metachar (``.``/``..``) fall
        back to ``"default"``.

        Returns:
            A directory ``Path`` guaranteed to sit below ``base_path``.
        """
        ns = namespace or "default"
        safe_ns = "".join(c for c in ns if c.isalnum() or c in "._-") or "default"
        if safe_ns in {".", ".."}:
            safe_ns = "default"
        ns_dir = (self.base_path / safe_ns).resolve()
        if not ns_dir.is_relative_to(self.base_path.resolve()):
            raise ValueError(f"namespace escapes base path: {namespace!r}")
        return ns_dir

    def _get_file_path(self, key: str, namespace: str | None) -> Path:
        ns_dir = self._get_ns_dir(namespace)
        # Sanitize key for filesystem
        safe_key = "".join(c for c in key if c.isalnum() or c in "._-")
        return ns_dir / f"{safe_key}{self.file_extension}"

    async def get(self, key: str, namespace: str | None = None) -> Any | None:
        file_path = self._get_file_path(key, namespace)
        if not file_path.exists():
            return None

        try:
            async with aiofiles.open(file_path) as f:
                content = await f.read()

            data = json.loads(content)

            # Check expiration
            expires_at_str = data.get("__expires_at")
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < datetime.now(UTC):
                    await self.delete(key, namespace)
                    return None

            return data.get("value")
        except Exception:  # noqa: BLE001 — read boundary never raises
            logger.exception("Error reading storage file %s", file_path)
            return None

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Persist a value under *key*, optionally with a time-to-live.

        TTL is stored as an ISO-8601 timestamp inside the JSON file and is
        **checked lazily** on each :meth:`get` call — there is no background
        eviction task.  Expired files remain on disk until they are next
        accessed (and then deleted automatically).

        Args:
            key: Storage key.
            value: JSON-serialisable Python value.
            namespace: Optional namespace (maps to a sub-directory).
            ttl: Seconds until the key expires.  ``None`` means no expiry.

        Returns:
            ``True`` on success, ``False`` on I/O or serialisation error.
        """
        file_path = self._get_file_path(key, namespace)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {"value": value}
        if ttl:
            expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
            data["__expires_at"] = expires_at.isoformat()

        # Atomic write using temp file
        temp_path = file_path.with_suffix(".tmp")
        indent = 2 if self.pretty_print else None

        try:
            content = json.dumps(data, indent=indent, default=str)
            async with aiofiles.open(temp_path, mode="wb") as f:
                await f.write(content)

            temp_path.replace(file_path)
            return True
        except Exception:  # noqa: BLE001 — write boundary never raises
            logger.exception("Error writing storage file %s", file_path)
            if temp_path.exists():
                temp_path.unlink()
            return False

    async def delete(self, key: str, namespace: str | None = None) -> bool:
        file_path = self._get_file_path(key, namespace)
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:  # noqa: BLE001 — delete boundary never raises
            logger.exception("Error deleting storage file %s", file_path)
            return False

    async def exists(self, key: str, namespace: str | None = None) -> bool:
        val = await self.get(key, namespace)
        return val is not None

    async def list_keys(
        self,
        pattern: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        ns_path = self._get_ns_dir(namespace)
        if not ns_path.exists():
            return []

        import fnmatch

        keys = []
        for file_path in ns_path.glob(f"*{self.file_extension}"):
            key = file_path.stem
            if pattern is None or fnmatch.fnmatch(key, pattern):
                # We should also check if it's expired, but for listing we might just return keys
                # A more robust implementation would check expiration here or during get
                keys.append(key)
        return keys

    async def clear(self, namespace: str | None = None) -> bool:
        ns = namespace or "default"
        ns_path = self._get_ns_dir(namespace)
        try:
            if ns_path.exists():
                shutil.rmtree(ns_path)
            return True
        except Exception:  # noqa: BLE001 — clear boundary never raises
            logger.exception("Error clearing namespace %s", ns)
            return False

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check accessibility of the base storage path.

        Performs a lightweight probe: ensures :attr:`base_path` exists and is
        writable.  Does **not** read or write any user data.

        Returns:
            :class:`~quadkit.contracts.HealthCheckResult` reflecting whether
            the underlying filesystem is accessible.
        """
        import time

        from quadkit.contracts import HealthCheckResult, HealthStatus

        start_ns = time.monotonic_ns()
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            probe = self.base_path / ".health_probe"
            probe.touch()
            probe.unlink()
            status = HealthStatus.HEALTHY
            message = "Local KV storage is accessible."
            error: str | None = None
        except OSError as exc:
            status = HealthStatus.UNHEALTHY
            message = "Local KV storage base path is not accessible."
            error = str(exc)

        duration_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        return HealthCheckResult(
            component="local_kv",
            status=status,
            message=message,
            error=error,
            duration_ms=duration_ms,
            details={"base_path": str(self.base_path)},
        )
