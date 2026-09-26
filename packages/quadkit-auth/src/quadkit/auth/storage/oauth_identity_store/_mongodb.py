"""MongoDB-backed OAuth identity store."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol


from quadkit.di.decorators import inject
from quadkit.logging import get_logger

logger = get_logger(__name__)

from quadkit.auth.storage.oauth_identity_store._protocol import (
    OAuthIdentity,
    OAuthIdentityStore,
)


@inject
class MongoDBOAuthIdentityStore(OAuthIdentityStore):
    """MongoDB-backed OAuth identity store"""

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        collection_name: str = "oauth_identities",
    ):
        self.db_provider = db_provider
        self.collection_name = collection_name
        self._initialized = False

    async def _ensure_collection(self) -> None:
        """Ensure collection exists with indexes"""
        if self._initialized:
            return

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]

        # Create indexes
        await collection.create_index([("user_id", 1)])
        await collection.create_index(
            [("provider", 1), ("provider_user_id", 1)],
            unique=True,
        )

        self._initialized = True

    async def _identity_from_doc(self, doc: dict[str, Any]) -> OAuthIdentity:
        """Convert MongoDB document to OAuthIdentity object"""
        return OAuthIdentity(
            user_id=doc["user_id"],
            provider=doc["provider"],
            provider_user_id=doc["provider_user_id"],
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )

    async def _doc_from_identity(self, identity: OAuthIdentity) -> dict[str, Any]:
        """Convert OAuthIdentity object to MongoDB document"""
        return {
            "user_id": identity.user_id,
            "provider": identity.provider,
            "provider_user_id": identity.provider_user_id,
            "created_at": identity.created_at,
            "updated_at": identity.updated_at,
        }

    async def create_oauth_identity(
        self,
        user_id: str,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity:
        """Create OAuth identity link"""
        await self._ensure_collection()

        identity = OAuthIdentity(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        doc = await self._doc_from_identity(identity)
        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        await collection.insert_one(doc)

        logger.info("Created OAuth identity: user=%s, provider=%s", user_id, provider)
        return identity

    async def get_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> OAuthIdentity | None:
        """Get OAuth identity by provider and provider user ID"""
        await self._ensure_collection()

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        doc = await collection.find_one(
            {"provider": provider, "provider_user_id": provider_user_id},
        )

        return await self._identity_from_doc(doc) if doc else None

    async def get_oauth_identities_for_user(
        self,
        user_id: str,
    ) -> list[OAuthIdentity]:
        """Get all OAuth identities for a user"""
        await self._ensure_collection()

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        cursor = collection.find({"user_id": user_id})

        identities = []
        async for doc in cursor:
            identity = await self._identity_from_doc(doc)
            identities.append(identity)

        return identities

    async def delete_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> bool:
        """Delete OAuth identity"""
        await self._ensure_collection()

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        result = await collection.delete_one(
            {"provider": provider, "provider_user_id": provider_user_id},
        )

        deleted = bool(result.deleted_count > 0)
        if deleted:
            logger.info(
                "Deleted OAuth identity: provider=%s, user_id=%s",
                provider,
                provider_user_id,
            )

        return deleted

    async def delete_oauth_identities_for_user(self, user_id: str) -> int:
        """Delete all OAuth identities for a user"""
        await self._ensure_collection()

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        result = await collection.delete_many({"user_id": user_id})

        deleted_count = int(result.deleted_count)
        if deleted_count > 0:
            logger.info(
                "Deleted %d OAuth identities for user %s",
                deleted_count,
                user_id,
            )

        return deleted_count

    async def get_user_by_oauth_identity(
        self,
        provider: str,
        provider_user_id: str,
    ) -> str | None:
        """Get local user_id by OAuth provider and external user ID."""
        await self._ensure_collection()

        collection = self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]
        doc = await collection.find_one(
            {"provider": provider, "provider_user_id": provider_user_id},
            {"user_id": 1},
        )

        return doc.get("user_id") if doc else None

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
            # It's a UUID - check if user exists in users collection
            await self._ensure_collection()
            self.db_provider.db[self.collection_name]  # type: ignore[attr-defined]

            # We need to check the users collection - assume it's named "users"
            users_collection = self.db_provider.db["users"]  # type: ignore[attr-defined]
            user_doc = await users_collection.find_one(
                {"_id": user_id_or_oauth_id},
                {"_id": 1},
            )

            return user_doc.get("_id") if user_doc else None
        # Not a UUID - treat as OAuth external ID
        return await self.get_user_by_oauth_identity(provider, user_id_or_oauth_id)

    def resolve_user_id_sync(
        self,
        external_id: str,
        provider: str = "google",
    ) -> str | None:
        """Synchronous resolution is not supported for database-backed store."""
        logger.warning(
            "sync_resolution_not_supported",
            provider=provider,
            external_id=external_id,
            store="MongoDBOAuthIdentityStore",
        )
        return None
