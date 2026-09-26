"""CockroachDB database driver implementation.

CockroachDB is wire-compatible with PostgreSQL, so this module reuses the
asyncpg-based :class:`~quadkit.sql.backends.postgres.PostgresConnectionPool`
with CockroachDB-appropriate defaults and DSN normalisation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any
import urllib.parse

from quadkit.contracts.core import HealthCheckResult
from quadkit.logging import get_logger
from quadkit.sql.backends.postgres import PostgresConnectionPool

logger = get_logger(__name__)

__all__ = ["CockroachDBConnection", "create_cockroachdb_pool"]

# CockroachDB default port (instead of PostgreSQL's 5432).
_CRDB_DEFAULT_PORT: int = 26257
_CRDB_DEFAULT_USER: str = "root"
_CRDB_DEFAULT_DB: str = "defaultdb"
_CRDB_SCHEME: str = "cockroachdb"
_PG_SCHEME: str = "postgresql"


class CockroachDBConnection(PostgresConnectionPool):
    """CockroachDB backend — PostgreSQL-compatible with CockroachDB-specific settings.

    CockroachDB is wire-compatible with PostgreSQL.  This driver reuses the
    same asyncpg-based connection pool as the PostgreSQL backend with
    CockroachDB-appropriate defaults (port 26257, user ``root``, database
    ``defaultdb``).

    Construct directly with individual host/port/user/password/database
    parameters, or use the convenience factory :func:`create_cockroachdb_pool`
    which accepts a DSN string and normalises the ``cockroachdb://`` scheme to
    ``postgresql://`` for asyncpg compatibility.

    Args:
        host: CockroachDB node hostname.
        port: CockroachDB SQL port.  Defaults to 26257.
        user: Database username.  Defaults to ``root``.
        password: Database password.
        database: Target database name.  Defaults to ``defaultdb``.
        **kwargs: Additional keyword arguments forwarded to
            :class:`~quadkit.sql.backends.postgres.PostgresConnectionPool`.
    """

    _COMPONENT_NAME: str = "cockroachdb"

    def __init__(
        self,
        host: str = "localhost",
        port: int = _CRDB_DEFAULT_PORT,
        user: str = _CRDB_DEFAULT_USER,
        password: str = "",
        database: str = _CRDB_DEFAULT_DB,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # DSN normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        """Translate ``cockroachdb://`` scheme to ``postgresql://`` for asyncpg.

        asyncpg does not recognise the ``cockroachdb://`` scheme.  This helper
        rewrites it to ``postgresql://`` while leaving all other DSN components
        untouched.

        Args:
            dsn: Source connection string.

        Returns:
            DSN string with ``postgresql://`` scheme.
        """
        if dsn.startswith(f"{_CRDB_SCHEME}://"):
            return f"{_PG_SCHEME}://" + dsn[len(f"{_CRDB_SCHEME}://") :]
        return dsn

    # ------------------------------------------------------------------
    # Pool creation override (CockroachDB-specific server_settings)
    # ------------------------------------------------------------------

    async def _create_pool(self, pool_kwargs: dict[str, Any]) -> None:
        """Create the asyncpg pool with CockroachDB-appropriate server_settings."""
        # CockroachDB accepts the same ``application_name`` server setting as
        # PostgreSQL; tag connections so they appear in CRDB's statement logs.
        server_settings: dict[str, str] = dict(
            pool_kwargs.pop("server_settings", {}) or {}
        )
        server_settings.setdefault("application_name", "quadkit-cockroachdb")
        pool_kwargs["server_settings"] = server_settings
        await super()._create_pool(pool_kwargs)

    # ------------------------------------------------------------------
    # Health check override (component name)
    # ------------------------------------------------------------------

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return health check result with ``component="cockroachdb"``.

        Delegates to the PostgreSQL pool health-check logic and replaces the
        generic ``"database"`` component name with ``"cockroachdb"``.

        Args:
            timeout: Max seconds for the health probe.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        result = await super().health_check(timeout)
        return replace(result, component=self._COMPONENT_NAME)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------


def create_cockroachdb_pool(
    dsn: str | None = None,
    *,
    host: str = "localhost",
    port: int = _CRDB_DEFAULT_PORT,
    user: str = _CRDB_DEFAULT_USER,
    password: str = "",
    database: str = _CRDB_DEFAULT_DB,
    min_size: int = 5,
    max_size: int = 20,
    **kwargs: Any,
) -> CockroachDBConnection:
    """Create a :class:`CockroachDBConnection` from a DSN string or explicit params.

    When *dsn* is provided, it is parsed and any ``cockroachdb://`` scheme is
    normalised to ``postgresql://``.  Explicit keyword arguments take precedence
    over DSN-derived values.

    Args:
        dsn: Optional connection string.  Supports both
            ``cockroachdb://user:pass@host:port/dbname`` and
            ``postgresql://...`` forms.
        host: CockroachDB node hostname (ignored when *dsn* is set).
        port: SQL port (ignored when *dsn* is set).
        user: Database username (ignored when *dsn* is set).
        password: Database password (ignored when *dsn* is set).
        database: Target database (ignored when *dsn* is set).
        min_size: Minimum asyncpg pool size.
        max_size: Maximum asyncpg pool size.
        **kwargs: Additional keyword arguments forwarded to
            :class:`CockroachDBConnection`.

    Returns:
        Configured :class:`CockroachDBConnection` (not yet connected).
    """
    resolved_host = host
    resolved_port = port
    resolved_user = user
    resolved_password = password
    resolved_database = database

    if dsn:
        normalized = CockroachDBConnection._normalize_dsn(dsn)
        parsed = urllib.parse.urlparse(normalized)
        resolved_host = parsed.hostname or host
        resolved_port = parsed.port or port
        resolved_user = urllib.parse.unquote(parsed.username or user)
        resolved_password = urllib.parse.unquote(parsed.password or password)
        resolved_database = (parsed.path or "").lstrip("/") or database
        logger.debug(
            "cockroachdb_dsn_parsed",
            host=resolved_host,
            port=resolved_port,
            database=resolved_database,
        )

    return CockroachDBConnection(  # type: ignore[abstract]
        host=resolved_host,
        port=resolved_port,
        user=resolved_user,
        password=resolved_password,
        database=resolved_database,
        min_size=min_size,
        max_size=max_size,
        **kwargs,
    )
