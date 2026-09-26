"""MongoDB-backed user store implementation.

Migrated to use ``DocumentStoreProtocol`` from ``the optional provider`` for
connection lifecycle and collection access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth.models.user import User, UserCredentials
from quadkit.di.decorators import inject
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.data import CollectionProtocol, DocumentStoreProtocol

logger = get_logger(__name__)


@inject
class MongoDBUserStore:
    """MongoDB-based user store using ``DocumentStoreProtocol``."""

    def __init__(
        self,
        document_store: DocumentStoreProtocol,
        collection_name: str = "users",
    ):
        self._store = document_store
        self.collection_name = collection_name
        self._collection: CollectionProtocol | None = None
        self._initialized = False

    @property
    def _col(self) -> CollectionProtocol:
        """Lazily initialize the collection handle."""
        if self._collection is None:
            self._collection = self._store.collection(self.collection_name)
        return self._collection

    async def _ensure_collection(self) -> None:
        """Ensure user collection exists."""
        if self._initialized:
            return
        # MongoDB collections are created automatically on first insert
        self._initialized = True

    async def _user_from_doc(self, doc: dict[str, Any]) -> User:
        """Convert MongoDB document to User object."""
        return User(
            user_id=doc["_id"],
            name=doc["name"] if "name" in doc else doc.get("username"),
            email=doc["email"],
            is_active=doc.get("is_active", True),
            is_verified=doc.get("is_verified", False),
            roles=doc.get("roles", []),
            permissions=doc.get("permissions", []),
            profile=doc.get("profile", {}),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            last_login_at=doc.get("last_login_at"),
            login_count=doc.get("login_count", 0),
        )

    async def _doc_from_user(self, user: User) -> dict[str, Any]:
        """Convert User object to MongoDB document (non-credential fields)."""
        return {
            "_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "roles": user.roles,
            "permissions": user.permissions,
            "profile": user.profile,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login_at": user.last_login_at,
            "login_count": user.login_count,
        }

    async def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str | None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        profile: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create a new user."""
        await self._ensure_collection()

        import uuid

        user_id = str(uuid.uuid4())

        user = User(
            user_id=user_id,
            name=name,
            email=email,
            roles=list(roles or []),
            permissions=list(permissions or []),
            profile=profile or {},
        )

        doc = await self._doc_from_user(user)
        doc["hashed_password"] = hashed_password
        doc["previous_passwords"] = []

        await self._col.insert_one(doc)

        logger.info("Created user: %s", name)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        await self._ensure_collection()

        doc = await self._col.find_one({"_id": user_id})
        return await self._user_from_doc(doc) if doc else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        await self._ensure_collection()

        doc = await self._col.find_one({"email": email})
        return await self._user_from_doc(doc) if doc else None

    async def update_user(self, user: User) -> None:
        """Update non-credential user information."""
        await self._ensure_collection()

        doc = await self._doc_from_user(user)
        await self._col.replace_one({"_id": user.user_id}, doc, upsert=True)

        logger.info("Updated user: %s", user.name)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        await self._ensure_collection()

        await self._col.delete_one({"_id": user_id})
        logger.info("Deleted user: %s", user_id)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination."""
        await self._ensure_collection()

        users = []
        cursor = self._col.find({}, skip=skip, limit=limit)
        async for doc in cursor:  # type: ignore[attr-defined]
            user = await self._user_from_doc(doc)
            users.append(user)

        return users

    async def count_users(self) -> int:
        """Count total users."""
        await self._ensure_collection()

        return await self._col.count_documents({})

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return credential data for *user_id*."""
        await self._ensure_collection()
        doc = await self._col.find_one(
            {"_id": user_id},
            projection={"hashed_password": 1, "previous_passwords": 1},
        )
        if not doc:
            return None
        return UserCredentials(
            user_id=user_id,
            hashed_password=doc.get("hashed_password"),
            previous_hashes=doc.get("previous_passwords", []),
        )

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credentials for the user."""
        await self._ensure_collection()
        await self._col.update_one(
            {"_id": creds.user_id},
            {
                "$set": {
                    "hashed_password": creds.hashed_password,
                    "previous_passwords": creds.previous_hashes,
                }
            },
        )
        logger.info("Updated credentials for user: %s", creds.user_id)


__all__ = ["MongoDBUserStore"]
