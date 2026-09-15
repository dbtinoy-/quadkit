from __future__ import annotations

import time
from typing import Any
import uuid


class TestDataFactory:
    """Factory for generating test data."""

    @staticmethod
    def create_user(user_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": user_id or str(uuid.uuid4()),
            "username": kwargs.get("username", f"user_{uuid.uuid4().hex[:8]}"),
            "email": kwargs.get("email", "user@example.com"),
            "roles": kwargs.get("roles", ["user"]),
            "created_at": kwargs.get("created_at", time.time()),
            **kwargs,
        }

    @staticmethod
    def create_task(task_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        return {
            "id": task_id or str(uuid.uuid4()),
            "name": kwargs.get("name", f"task_{uuid.uuid4().hex[:8]}"),
            "status": kwargs.get("status", "pending"),
            "priority": kwargs.get("priority", "normal"),
            "created_at": kwargs.get("created_at", time.time()),
            **kwargs,
        }

    @staticmethod
    def create_message(topic: str = "test", **kwargs: Any) -> dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "topic": topic,
            "payload": kwargs.get("payload", {"test": True}),
            "timestamp": kwargs.get("timestamp", time.time()),
            **kwargs,
        }

    @staticmethod
    def create_request(
        method: str = "GET",
        path: str = "/",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {
            "method": method,
            "path": path,
            "headers": kwargs.get("headers", {}),
            "query_params": kwargs.get("query_params", {}),
            "body": kwargs.get("body"),
            "timestamp": kwargs.get("timestamp", time.time()),
            **kwargs,
        }


test_data_factory = TestDataFactory()
