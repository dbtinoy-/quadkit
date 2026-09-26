"""SQLAlchemy-backed OAuth identity store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol


from quadkit.auth.storage.oauth_identity_store._protocol import (
    OAuthIdentity,
    OAuthIdentityStore,
)
from quadkit.di.decorators import inject


@inject
class SQLAlchemyOAuthIdentityStore(OAuthIdentityStore):
    """Database-backed OAuth identity store"""

    def __init__(self, db_provider: DatabaseProviderProtocol):
        self.db_provider = db_provider
        self._initialized = False

    async def _ensure_tables(self) -> None:
        """Ensure oauth_identities table exists."""
        if self._initialized:
            return

        create_sql = """
        CREATE TABLE IF NOT EXISTS oauth_identities (
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (provider, provider_user_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_oauth_identities_user_id ON oauth_identities(user_id);
        """

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            for statement in create_sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    await conn.execute(stmt)

        self._initialized = True

    async def _identity_from_row(self, row: Any) -> OAuthIdentity:
        """Convert database row to OAuthIdentity object"""
        return OAuthIdentity(
            user_id=row.get("user_id"),
            provider=row.get("provider"),
            provider_user_id=row.get("provider_user_id"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    async def create_oauth_identity(
        self,
        user_id: str,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity:
        """Create OAuth identity link"""
        await self._ensure_tables()

        identity = OAuthIdentity(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        insert_sql = """
        INSERT INTO oauth_identities
        (user_id, provider, provider_user_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            await conn.execute(
                insert_sql,
                [
                    identity.user_id,
                    identity.provider,
                    identity.provider_user_id,
                    identity.created_at,
                    identity.updated_at,
                ],
            )

        logger.info("Created OAuth identity: user=%s, provider=%s", user_id, provider)
        return identity

    async def get_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity | None:
        """Get OAuth identity by provider and provider user ID"""
        await self._ensure_tables()

        select_sql = """
        SELECT * FROM oauth_identities
        WHERE provider = ? AND provider_user_id = ?
        """

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            result = await conn.execute(select_sql, [provider, provider_user_id])
            row = result.rows[0] if result.rows else None

        return await self._identity_from_row(row) if row else None

    async def get_oauth_identities_for_user(
        self,
        user_id: str,
    ) -> list[OAuthIdentity]:
        """Get all OAuth identities for a user"""
        await self._ensure_tables()

        select_sql = "SELECT * FROM oauth_identities WHERE user_id = ?"

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            result = await conn.execute(select_sql, [user_id])
            rows = result.rows

        identities = []
        for row in rows:
            identity = await self._identity_from_row(row)
            identities.append(identity)

        return identities

    async def delete_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> bool:
        """Delete OAuth identity"""
        await self._ensure_tables()

        delete_sql = """
        DELETE FROM oauth_identities
        WHERE provider = ? AND provider_user_id = ?
        """

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            result = await conn.execute(delete_sql, [provider, provider_user_id])
            deleted = bool(result.row_count > 0)  # Coerce to bool for typing stability

        if deleted:
            logger.info(
                "Deleted OAuth identity: provider=%s, user_id=%s",
                provider,
                provider_user_id,
            )

        return deleted

    async def delete_oauth_identities_for_user(self, user_id: str) -> int:
        """Delete all OAuth identities for a user"""
        await self._ensure_tables()

        delete_sql = "DELETE FROM oauth_identities WHERE user_id = ?"

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            result = await conn.execute(delete_sql, [user_id])
            deleted_count = int(result.row_count)

        if deleted_count > 0:
            logger.info(
                "Deleted %d OAuth identities for user %s",
                deleted_count,
                user_id,
            )

        return int(deleted_count)

    async def get_user_by_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> str | None:
        """Get local user_id by OAuth provider and external user ID."""
        await self._ensure_tables()

        select_sql = """
        SELECT user_id FROM oauth_identities
        WHERE provider = ? AND provider_user_id = ?
        """

        async with self.db_provider.scoped_context():
            conn = await self.db_provider.get_scoped_connection()
            result = await conn.execute(select_sql, [provider, provider_user_id])
            row = result.rows[0] if result.rows else None

        return row.get("user_id") if row else None

    async def resolve_user_id(
        self,
        user_id_or_oauth_id: str,
        provider: str = "google",
    ) -> str | None:
        """Resolve user_id from either UUID or OAuth external ID.

        Resolution logic:
        1. If user_id_or_oauth_id is a valid UUID format, check if user exists
        2. If not a valid UUID, treat it as an OAuth provider_user_id and look up
        """
        import re

        # Check if it's a valid UUID format
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )

        is_uuid = bool(uuid_pattern.match(user_id_or_oauth_id))

        if is_uuid:
            # It's a UUID - check if user exists
            await self._ensure_tables()
            check_user_sql = "SELECT user_id FROM users WHERE user_id = ?"

            async with self.db_provider.scoped_context():
                conn = await self.db_provider.get_scoped_connection()
                result = await conn.execute(check_user_sql, [user_id_or_oauth_id])
                row = result.rows[0] if result.rows else None

            return row.get("user_id") if row else None
        # Not a UUID - treat as OAuth external ID
        return await self.get_user_by_oauth_identity(provider, user_id_or_oauth_id)

    def resolve_user_id_sync(
        self,
        external_id: str,
        provider: str = "google",
    ) -> str | None:
        """Synchronous resolution is not supported for database-backed store.

        This method is required by IdentityResolverProtocol but cannot be
        implemented safely for an async database provider.
        """
        logger.warning(
            "sync_resolution_not_supported",
            provider=provider,
            external_id=external_id,
            store="SQLAlchemyOAuthIdentityStore",
        )
        return None
