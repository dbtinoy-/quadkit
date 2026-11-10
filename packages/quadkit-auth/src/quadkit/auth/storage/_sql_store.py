"""SQL-backed user store implementation."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.auth.exceptions import EmailExistsError, UsernameExistsError
from quadkit.auth.models.user import User, UserCredentials
from quadkit.contracts.data.sql.database import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.serialization import loads

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)

#: The identifier rule a configured table name must satisfy before any
#: SQL is built from it — the same shape the framework's SQL surface
#: accepts for identifiers (``quadkit.sql.search`` uses this rule).
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _require_database_success(result: Any) -> None:
    """Reject reported provider failures without exposing database details.

    Legacy provider results may be lists, dicts or scalars without a success
    flag. The canonical Quadkit result objects explicitly report failure.
    """
    if isinstance(result, (QueryResult, InsertResult, UpdateResult, DeleteResult)):
        if result.success is not True:
            raise RuntimeError("identity store database operation failed")
    elif getattr(result, "success", None) is False:
        raise RuntimeError("identity store database operation failed")


def _sql_true(value: Any) -> bool:
    """Accept only boolean true and the integer one returned by SQL drivers."""
    return value is True or (type(value) is int and value == 1)


@inject
class SQLUserStore:
    """Database-backed user store — the persistent identity store.

    Uses the ``DatabaseProvider`` API from ``quadkit.contracts`` (the
    ``quadkit.sql`` providers implement it), so no SQLAlchemy dependency
    is involved. The public API mirrors :class:`UserStoreProtocol` from
    ``token_store``, including the ``ValueError`` uniqueness contract of
    :class:`InMemoryUserStore`.

    The store owns its table: :meth:`initialize` creates it (and the
    unique email/name indexes) when missing, idempotently, and every
    public method ensures initialization before its first query — there
    is no migration tool between this store and a working application.
    The table name is configurable (default ``users``) and validated
    before any SQL is constructed; every statement uses that one
    configured identifier.
    """

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        table_name: str = "users",
    ) -> None:
        if not _TABLE_NAME_RE.fullmatch(table_name):
            raise ValueError(
                f"Invalid users table name {table_name!r}: must be a plain "
                "SQL identifier (letters, digits, underscores; not "
                "starting with a digit)."
            )
        self.db_provider = db_provider
        self.table_name = table_name
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Whether :meth:`initialize` has created/verified the table."""
        return self._initialized

    async def initialize(self) -> None:
        """Create the users table and indexes when missing (idempotent).

        Called by the authentication provider during boot so a broken
        identity database fails startup honestly instead of the first
        login; every store method also calls it, so direct use without
        the provider works too.
        """
        await self._ensure_tables()

    async def _ensure_tables(self) -> None:
        """Ensure the users table exists before the first auth query."""
        if self._initialized:
            return
        table = f'"{self.table_name}"'
        result = await self.db_provider.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "user_id TEXT PRIMARY KEY, "
            "email TEXT NOT NULL, "
            "name TEXT NOT NULL, "
            "hashed_password TEXT, "
            "is_admin BOOLEAN NOT NULL DEFAULT FALSE, "
            "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
            "is_verified BOOLEAN NOT NULL DEFAULT FALSE, "
            "roles TEXT NOT NULL DEFAULT '[]', "
            "permissions TEXT NOT NULL DEFAULT '[]', "
            "previous_passwords TEXT NOT NULL DEFAULT '[]', "
            "profile TEXT NOT NULL DEFAULT '{}', "
            "created_at TEXT, "
            "updated_at TEXT, "
            "last_login_at TEXT, "
            "login_count INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        _require_database_success(result)
        result = await self.db_provider.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_name}_email "
            f"ON {table}(email)"
        )
        _require_database_success(result)
        result = await self.db_provider.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.table_name}_name "
            f"ON {table}(name)"
        )
        _require_database_success(result)
        self._initialized = True

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
            is_active=_sql_true(row.get("is_active")),
            is_verified=_sql_true(row.get("is_verified")),
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

    async def _exists(self, column: str, value: str) -> bool:
        """Whether a row carries *value* in the ``name``/``email`` column."""
        if column not in ("name", "email"):
            raise ValueError(f"Unsupported uniqueness column: {column!r}")
        result = await self.db_provider.execute_query(
            f'SELECT user_id FROM "{self.table_name}" WHERE {column} = ?',
            [value],
        )
        _require_database_success(result)
        rows = result.rows if hasattr(result, "rows") else result
        return bool(rows)

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
        """Create a new user using the canonical DatabaseProvider API."""
        import uuid

        await self._ensure_tables()

        # Same uniqueness contract as InMemoryUserStore (name, then
        # email); the unique indexes back it at the database level.
        if await self._exists("name", name):
            raise UsernameExistsError(f"Name '{name}' already exists")
        if await self._exists("email", email):
            raise EmailExistsError(f"Email '{email}' already exists")

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

        now = datetime.now(UTC).isoformat()
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
            "created_at": now,
            "updated_at": now,
        }

        result = await self.db_provider.execute_insert(self.table_name, payload)
        _require_database_success(result)

        logger.info("Created user: %s", name)
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID"""
        await self._ensure_tables()
        select_sql = f'SELECT * FROM "{self.table_name}" WHERE user_id = ?'

        # Use provider-level execute_query for a consistent result shape
        result = await self.db_provider.execute_query(select_sql, [user_id])
        _require_database_success(result)
        rows = result.rows if hasattr(result, "rows") else result
        row = (
            rows[0]
            if isinstance(rows, list) and rows
            else (rows if isinstance(rows, dict) else None)
        )

        return await self._user_from_row(row) if row else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email"""
        await self._ensure_tables()
        select_sql = f'SELECT * FROM "{self.table_name}" WHERE email = ?'

        result = await self.db_provider.execute_query(select_sql, [email])
        _require_database_success(result)
        rows = result.rows if hasattr(result, "rows") else result
        row = (
            rows[0]
            if isinstance(rows, list) and rows
            else (rows if isinstance(rows, dict) else None)
        )

        return await self._user_from_row(row) if row else None

    async def update_user(self, user: User) -> None:
        """Update non-credential user information."""
        await self._ensure_tables()
        payload = {
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "roles": user.roles,
            "permissions": user.permissions,
            "profile": user.profile,
            "last_login_at": (
                user.last_login_at.isoformat()
                if isinstance(user.last_login_at, datetime)
                else user.last_login_at
            ),
            "login_count": user.login_count,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        result = await self.db_provider.execute_update(
            self.table_name,
            payload,
            "user_id = ?",
            [user.user_id],
        )

        _require_database_success(result)
        logger.info("Updated user: %s", user.name)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        await self._ensure_tables()
        result = await self.db_provider.execute_delete(
            self.table_name, "user_id = ?", [user_id]
        )
        _require_database_success(result)

        logger.info("Deleted user: %s", user_id)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination"""
        await self._ensure_tables()
        select_sql = (
            f'SELECT * FROM "{self.table_name}" '
            "ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )

        result = await self.db_provider.execute_query(select_sql, [limit, skip])
        _require_database_success(result)
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
        await self._ensure_tables()
        count_sql = f'SELECT COUNT(*) as count FROM "{self.table_name}"'

        result = await self.db_provider.execute_query(count_sql)
        _require_database_success(result)
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
        await self._ensure_tables()
        select_sql = (
            "SELECT user_id, hashed_password, previous_passwords "
            f'FROM "{self.table_name}" WHERE user_id = ?'
        )
        result = await self.db_provider.execute_query(select_sql, [user_id])
        _require_database_success(result)
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
        await self._ensure_tables()
        payload = {
            "hashed_password": creds.hashed_password,
            "previous_passwords": creds.previous_hashes,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        result = await self.db_provider.execute_update(
            self.table_name,
            payload,
            "user_id = ?",
            [creds.user_id],
        )
        _require_database_success(result)
        logger.info("Updated credentials for user: %s", creds.user_id)


__all__ = ["SQLUserStore"]
