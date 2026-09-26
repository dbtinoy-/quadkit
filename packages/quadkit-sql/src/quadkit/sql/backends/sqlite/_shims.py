"""Optional-dependency availability shims shared by sqlite backend modules."""

from typing import Any

# Declare optional third-party/runtime names as Any so we can provide runtime fallbacks
aiosqlite: Any = None
try:
    import aiosqlite  # noqa: F401 — patched by tests via backend modules

    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


HAS_MONITORING = False
try:
    from quadkit.sql.monitoring import DatabaseMonitor as _RealDatabaseMonitor

    DatabaseMonitor = _RealDatabaseMonitor
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False
    DatabaseMonitor = None  # type: ignore[assignment,misc]
