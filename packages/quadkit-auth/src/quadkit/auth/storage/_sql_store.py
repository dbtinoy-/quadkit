"""SQL-backed user store implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.auth.models.user import User, UserCredentials
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.serialization import loads

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)


@inject
class SQLUserStore:
    """Database-based user store (SQL-backed implementation)

    This implementation uses the `DatabaseProvider` API from `quadkit.sql` to
    perform SQL operations directly, removing the hard dependency on
    SQLAlchemy. It preserves the original public interface expected by
    callers/tests while delegating to the canonical database provider.

    The public API mirrors :class:`UserStoreProtocol` defined in ``token_store``
    including optional keyword arguments for backwards compatibility.
    """

    def __init__(self, db_provider: DatabaseProviderProtocol):
        self.db_provider = db_provider
        self._initialized = False

    async def _ensure_tables(self) -> None:
        """Ensure user table exists (Managed by Alembic migrations)."""
        # We rely on Alembic migrations to manage the schema
        # This prevents the application from trying to create a conflicting schema

    async def _user_from_row(self, row: Any) -> User:
        """Convert database row to User object"""

        def safe_load(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return val
            try:
                return loads(val)
            except (ValueError, TypeError, json.JSONDecodeError):
                return default

        return User(
            user_id=str(row.get("user_id")),
            name=row.get("name") or row.get("username"),
            email=row.get("email"),
            is_active=bool(row.get("is_active", True)),
            is_verified=bool(row.get("is_verified", False)),
            roles=safe_load(row.get("roles"), []),
            permissions=safe_load(row.get("permissions"), []),
            profile=safe_load(row.get("profile"), {}),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            last_login_at=row.get("last_login_at"),
            login_count=int(row.get("login_count", 0)),
        )

    def _credentials_from_row(self, row: Any) -> UserCredentials:
        """Extract credential data from a database row."""

        def safe_load(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return val
            try:
                return loads(val)
            except (ValueError, TypeError, json.JSONDecodeError):
                return default

        return UserCredentials(
            user_id=str(row.get("user_id")),
            hashed_password=row.get("hashed_password"),
            previous_hashes=safe_load(row.get("previous_passwords"), []),
        )

    async def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        profile: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> User:
        """Create a new user using the canonical DatabaseProvider API."""
        import uuid

        user_id = str(uuid.uuid4())

        is_verified = bool(kwargs.get("is_verified", False))

        user = User(
            user_id=user_id,
            name=name,
            email=email,
            roles=list(roles or []),
            permissions=list(permissions or []),
            profile=profile or {},
            is_verified=is_verified,
        )

        # Prefer provider-level convenience method for portability and consistent return shape
        payload = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "hashed_password": hashed_password,
            "is_admin": False,
            "is_active": True,
            "is_verified": is_verified,
            "roles": roles or [],
            "permissions": permissions or [],
            "previous_passwords": [],
            "profile": profile or {},
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

        await self.db_provider.execute_insert("users", payload)

        logger.info("Created user: %s", name)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        select_sql = "SELECT * FROM users WHERE user_id = ?"

        # Use provider-level execute_query for a consistent result shape
        result = await self.db_provider.execute_query(select_sql, [user_id])
        rows = result.rows if hasattr(result, "rows") else result
        row = (
            rows[0]
            if isinstance(rows, list) and rows
            else (rows if isinstance(rows, dict) else None)
        )

        return await self._user_from_row(row) if row else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email"""
        select_sql = "SELECT * FROM users WHERE email = ?"

        result = await self.db_provider.execute_query(select_sql, [email])
        rows = result.rows if hasattr(result, "rows") else result
        row = (
            rows[0]
            if isinstance(rows, list) and rows
            else (rows if isinstance(rows, dict) else None)
        )

        return await self._user_from_row(row) if row else None

    async def update_user(self, user: User) -> None:
        """Update non-credential user information."""
        payload = {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "roles": user.roles,
            "permissions": user.permissions,
            "profile": user.profile,
            "last_login_at": user.last_login_at,
            "login_count": user.login_count,
            "updated_at": datetime.now(UTC),
        }

        await self.db_provider.execute_update(
            "users",
            payload,
            "user_id = ?",
            [user.user_id],
        )

        logger.info("Updated user: %s", user.name)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        await self.db_provider.execute_delete("users", "user_id = ?", [user_id])

        logger.info("Deleted user: %s", user_id)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination"""
        select_sql = "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?"

        result = await self.db_provider.execute_query(select_sql, [limit, skip])
        rows = result.rows if hasattr(result, "rows") else result
        normalized_rows = (
            rows
            if isinstance(rows, list)
            else ([rows] if isinstance(rows, dict) else [])
        )

        users = []
        for row in normalized_rows:
            user = await self._user_from_row(row)
            users.append(user)

        return users

    async def count_users(self) -> int:
        """Count total users"""
        count_sql = "SELECT COUNT(*) as count FROM users"

        result = await self.db_provider.execute_query(count_sql)
        rows = result.rows if hasattr(result, "rows") else result
        if isinstance(rows, list) and rows:
            row = rows[0]
        elif isinstance(rows, dict):
            row = rows
        else:
            row = None

        count = row.get("count") if row else 0
        return int(count or 0)

    async def get_credentials(self, user_id: str) -> UserCredentials | None:
        """Return credential data for *user_id* from the database."""
        select_sql = (
            "SELECT user_id, hashed_password, previous_passwords "
            "FROM users WHERE user_id = ?"
        )
        result = await self.db_provider.execute_query(select_sql, [user_id])
        rows = result.rows if hasattr(result, "rows") else result
        row = (
            rows[0]
            if isinstance(rows, list) and rows
            else (rows if isinstance(rows, dict) else None)
        )
        if not row:
            return None
        return self._credentials_from_row(row)

    async def update_credentials(self, creds: UserCredentials) -> None:
        """Persist updated credential data for ``creds.user_id``."""

        def safe_load(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (list, dict)):
                return val
            try:
                return loads(val)
            except (ValueError, TypeError, json.JSONDecodeError):
                return default

        payload = {
            "hashed_password": creds.hashed_password,
            "previous_passwords": creds.previous_hashes,
            "updated_at": datetime.now(UTC),
        }
        await self.db_provider.execute_update(
            "users",
            payload,
            "user_id = ?",
            [creds.user_id],
        )
        logger.info("Updated credentials for user: %s", creds.user_id)


__all__ = ["SQLUserStore"]
