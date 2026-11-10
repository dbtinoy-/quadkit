"""Application-owned publication transaction using native identity/delivery APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.storage import SQLUserStore
from quadkit.contracts.notification.delivery import DeliveryStatus
from quadkit.notification.delivery import (
    InboxDeliveryChannel,
    NotificationDeliveryDispatcher,
    SqlDeliveryStore,
    flush_retries,
)
from quadkit.notification.inbox.database import DatabaseInboxStore
from quadkit.notification.inbox.service import InboxService

if TYPE_CHECKING:
    from starlette.requests import Request

    from quadkit.auth.models.user import User
    from quadkit.contracts.data import DatabaseProviderProtocol
    from quadkit.validation import SecretStr


class PublicationRefusedError(Exception):
    """An expected business refusal, safe to return without database details."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


class TrustedPublication:
    """One publication and its durable delivery intent share one SQL provider.

    Delivery is a separate post-commit worker. Neither failed delivery nor a
    lost worker acknowledgement requires repeating the business publication.
    No account, recipient or credential is inferred from request metadata.
    """

    def __init__(
        self,
        database: DatabaseProviderProtocol,
        recipient_email: str,
        token_secret: SecretStr,
    ) -> None:
        self.database = database
        self.users = SQLUserStore(database)
        self.tokens = JWTTokenManager(
            current_key_id="editorial",
            keys={"editorial": token_secret},
            required_audience="editorial-notifications",
            access_expiration_hours=1,
        )
        self.inbox = InboxService(DatabaseInboxStore(database))
        self.channel = InboxDeliveryChannel(
            self.inbox, self.users.get_user_by_email, recipient_email=recipient_email
        )
        self.queue = SqlDeliveryStore(database, table="editorial_inbox_delivery")
        self.dispatcher = NotificationDeliveryDispatcher([self.channel])

    async def initialize(self) -> None:
        """Bootstrap committed schema before serving or beginning a business UOW."""
        await self.users.initialize()
        await self.queue.initialize()
        result = await self.database.execute(
            "CREATE TABLE IF NOT EXISTS editorial_posts ("
            "id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "status TEXT NOT NULL CHECK(status IN ('draft', 'published')))"
        )
        if not result.success:
            raise RuntimeError("Publication schema initialization failed")

    async def authenticate(self, request: Request) -> User | None:
        """Verify a native signed access token and resolve fresh account status."""
        headers = request.headers.getlist("authorization")
        if len(headers) != 1:
            return None
        scheme, separator, token = headers[0].partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not token
            or any(c.isspace() for c in token)
        ):
            return None
        verified = await self.tokens.verify_token(token)
        if verified.is_err():
            return None
        subject = verified.unwrap().user_id
        user = await self.users.get_user_by_id(subject)
        if user is None or user.user_id != subject or user.is_active is not True:
            return None
        return user

    async def subject(self, request: Request) -> str | None:
        """Trusted resolver consumed by the native recipient-scoped inbox adapter."""
        user = await self.authenticate(request)
        return user.user_id if user else None

    async def publisher(self, request: Request) -> None:
        """Require a fresh explicit permission; token claims alone do not grant it."""
        user = await self.authenticate(request)
        if user is None:
            raise PublicationRefusedError(401, "Authentication required")
        if "editorial:publish" not in user.permissions:
            raise PublicationRefusedError(403, "Publication permission required")

    async def create(self, title: str) -> dict[str, str]:
        """Create a draft; caller cannot select state, identity or recipient."""
        key = str(uuid4())
        result = await self.database.execute(
            "INSERT INTO editorial_posts (id, title, status) VALUES (?, ?, 'draft')",
            [key, title],
        )
        if not result.success:
            raise RuntimeError("Draft creation failed")
        return {"id": key, "title": title, "status": "draft"}

    async def publish(self, key: str) -> dict[str, str]:
        """Atomically commit the conditional business write and pinned envelope."""
        found = await self.database.execute_query(
            "SELECT title, status FROM editorial_posts WHERE id = ?", [key]
        )
        if not found.success:
            raise RuntimeError("Publication read failed")
        if not found.rows:
            raise PublicationRefusedError(404, "Post not found")
        row = found.rows[0]
        if row["status"] != "draft":
            raise PublicationRefusedError(409, "Post is not a draft")
        title = str(row["title"])
        prepared = await self.channel.prepare(
            f"post-published:v1:{key}",
            "Post published",
            title,
            post_id=key,
            status="published",
        )
        if prepared.is_err():
            raise PublicationRefusedError(
                503, "Configured notification recipient unavailable"
            )
        async with self.database.transaction():
            updated = await self.database.execute_query(
                "UPDATE editorial_posts SET status = 'published' "
                "WHERE id = ? AND status = 'draft' AND title = ? RETURNING id",
                [key, title],
            )
            if not updated.success:
                raise RuntimeError("Publication write failed")
            if not updated.rows:
                raise PublicationRefusedError(409, "Post changed during publication")
            delivery_id = await self.queue.create_pending(prepared.unwrap())
        return {
            "id": key,
            "status": "published",
            "delivery_id": delivery_id,
            "notification": "queued",
        }

    async def search(self, query: str) -> list[dict[str, object]]:
        """Bounded literal title search; no FTS/operator or public-feed claim."""
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = await self.database.execute_query(
            "SELECT id, title, status FROM editorial_posts "
            "WHERE title LIKE ? ESCAPE '\\' ORDER BY id LIMIT 100",
            [f"%{escaped}%"],
        )
        if not result.success:
            raise RuntimeError("Publication search failed")
        return [dict(row) for row in result.rows]

    async def flush(self) -> int:
        """Run the existing lease/backoff/dead-letter worker, outside publication."""
        return await flush_retries(self.queue, self.dispatcher)

    async def redrive(self, delivery_id: str) -> str:
        """Operator-only recovery: retain the original pinned immutable intent.

        A new queue row preserves history and the original effect key. Never
        re-resolve/re-pin a different recipient or retry business publication.
        Native send_once still prevents duplicate messages after a lost ack.
        """
        record = await self.queue.get_delivery(delivery_id)
        if record is None or record.status != DeliveryStatus.FAILED:
            raise ValueError("Only an existing failed delivery can be redriven")
        if record.message.channel != "inbox":
            raise ValueError("Only the isolated inbox channel can be redriven")
        return await self.queue.create_pending(record.message)
