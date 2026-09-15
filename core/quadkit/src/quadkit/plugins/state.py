"""Boot-readable file mirror of admin-toggled plugin disabled state.

Bridges "admin clicked disable" to "next process boot excludes it" without
core ever gaining a DB dependency — this module has zero knowledge of
``TenantConfigStore`` or any other admin/DB concept, deliberately, per the
package-boundary rule (extensions never depend on each other).

Persistence contract (systemd-preset style):
  - Every save is atomic: tempfile + fsync + ``os.replace``. A crash leaves
    either the old or the new file, never a torn one.
  - Read-modify-write is serialized with a ``flock`` advisory lock so
    concurrent admin sessions in different processes cannot clobber each
    other's update.
  - A corrupt state file is renamed to ``<name>.corrupt-<ts>`` and reading
    fails open to an empty set — plugin state must never block boot.

Note:
    File integrity: ``plugins.json`` is treated as operator-owned and is
    intentionally *not* tamper-evident (no signature/HMAC). Write access to
    the file already implies full filesystem trust, and its ``disabled``
    entries are only membership-tested against discovered entry points, so
    the file cannot be used to inject code. This acceptance is deliberate —
    see ``docs/superpowers/specs/2026-08-16-security-plugins-design.md``.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.plugins.exceptions import PluginStateError
from quadkit.serialization import JSONDecodeError, dumps_str, loads_str

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = get_logger(__name__)

__all__ = ["_STATE_SCHEMA_VERSION", "load_disabled", "save_disabled", "update_disabled"]

_STATE_SCHEMA_VERSION = 1
_ENV_STATE_PATH = "QUADKIT_PLUGINS_STATE_PATH"
_DEFAULT_STATE_PATH = Path(".quadkit/plugins.json")


def _resolve_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    env_value = os.environ.get(_ENV_STATE_PATH)
    return Path(env_value) if env_value else _DEFAULT_STATE_PATH


def _lock_file_for(resolved: Path) -> Path:
    return resolved.with_name(resolved.name + ".lock")


def _write_atomic(resolved: Path, data: dict[str, Any]) -> None:
    """Write ``data`` to ``resolved`` atomically via temp + fsync + replace."""
    temp = resolved.with_name(f"{resolved.name}.tmp-{os.getpid()}")
    try:
        with temp.open("w") as fh:
            fh.write(dumps_str(data))
            fh.flush()
            os.fsync(fh.fileno())
        temp.replace(resolved)
    except OSError as exc:
        try:
            temp.unlink()
        except OSError:
            pass
        raise PluginStateError(
            "failed to write plugin state",
            path=str(resolved),
        ) from exc


def _fail_open_corrupt(resolved: Path, reason: str) -> set[str]:
    """Back up a corrupt ``resolved`` file and fail open to an empty set.

    Preserves the original bytes as ``<name>.corrupt-<ts>`` for operator
    inspection and returns an empty set so plugin state never blocks boot.

    Args:
        resolved: State-file path.
        reason: Logged cause (e.g. ``"unparseable_json"``).

    Returns:
        Always the empty set.
    """
    backup = resolved.with_name(f"{resolved.name}.corrupt-{int(time.time())}")
    try:
        resolved.replace(backup)
        logger.warning(
            "plugins.state.corrupt_file_backed_up",
            path=str(resolved),
            backup=str(backup),
            reason=reason,
        )
    except OSError:
        logger.warning(
            "plugins.state.corrupt_file_unreadable",
            path=str(resolved),
            error="backup_failed",
            reason=reason,
        )
    return set()


def load_disabled(path: str | Path | None = None) -> set[str]:
    """Return the set of plugin names disabled in the boot-file mirror.

    Missing or corrupt state never prevents application boot — a corrupt
    file is preserved as ``<name>.corrupt-<ts>`` and reading returns an
    empty set. Legacy unversioned files (``{"disabled": [...]}``) load fine.

    Args:
        path: Explicit state-file path. Falls back to the
            ``QUADKIT_PLUGINS_STATE_PATH`` env var, then
            ``.quadkit/plugins.json`` relative to the working directory.

    Returns:
        Set of disabled entry-point names (possibly empty).
    """
    resolved = _resolve_path(path)
    if not resolved.exists():
        return set()

    try:
        data = loads_str(resolved.read_text())
    except (JSONDecodeError, OSError):
        return _fail_open_corrupt(resolved, "unparseable_json")

    version = data.get("version")
    if version is not None and (
        not isinstance(version, int) or version != _STATE_SCHEMA_VERSION
    ):
        return _fail_open_corrupt(resolved, f"unsupported_version={version!r}")

    disabled = data.get("disabled", [])
    if not isinstance(disabled, list):
        logger.warning("plugins.state.invalid_shape", path=str(resolved))
        return set()
    return {str(name) for name in disabled}


def save_disabled(names: set[str], path: str | Path | None = None) -> None:
    """Persist ``names`` to the boot-file mirror under an exclusive lock.

    Atomic (temp + fsync + ``os.replace``) and serialized via ``flock``
    so concurrent writers cannot interleave read-modify-write cycles.

    Args:
        names: Set of disabled plugin entry-point names.
        path: Explicit state-file path (env var / default fallback applies
            when omitted).

    Raises:
        PluginStateError: If the state cannot be written (disk full,
            permission denied, etc.).
    """
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    with _exclusive_lock(resolved):
        data: dict[str, Any] = {
            "version": _STATE_SCHEMA_VERSION,
            "disabled": sorted(names),
        }
        _write_atomic(resolved, data)


def update_disabled(
    mutator: Any,
    path: str | Path | None = None,
) -> set[str]:
    """Apply ``mutator`` to the disabled set under one exclusive lock.

    Load, mutate, and save happen inside a single ``flock`` critical
    section, so concurrent readers/writers (e.g. two admin sessions in
    different processes) cannot lose updates.

    Args:
        mutator: Callable mapping the current disabled set to the new
            disabled set, e.g. ``lambda current: current | {"rag"}``.
        path: Explicit state-file path (env var / default fallback applies
            when omitted).

    Returns:
        The resulting disabled set after ``mutator`` was applied.

    Raises:
        PluginStateError: If the state cannot be read or written.
    """
    resolved = _resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    with _exclusive_lock(resolved):
        current = load_disabled(resolved)
        updated = mutator(current)
        data: dict[str, Any] = {
            "version": _STATE_SCHEMA_VERSION,
            "disabled": sorted(updated),
        }
        _write_atomic(resolved, data)
    return set(updated)


def _exclusive_lock(resolved: Path) -> Any:
    """Return a context manager holding an exclusive ``flock`` on the
    sibling ``.lock`` file for ``resolved``."""
    lock_path = _lock_file_for(resolved)

    @contextlib.contextmanager
    def _locked() -> Iterator[None]:
        with lock_path.open("a") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    return _locked()
