"""Tests for testing.utils.factory module."""

import time

from quadkit.testing.lib.factory import TestDataFactory


class TestTestDataFactory:
    """Tests for TestDataFactory."""

    def test_create_user_default(self) -> None:
        """Test create_user with default values."""
        user = TestDataFactory.create_user()

        assert user["id"] is not None
        assert user["username"] is not None
        assert user["email"] == "user@example.com"
        assert user["roles"] == ["user"]
        assert "created_at" in user

    def test_create_user_with_custom_id(self) -> None:
        """Test create_user with custom ID."""
        user = TestDataFactory.create_user(user_id="test-123")

        assert user["id"] == "test-123"

    def test_create_user_with_custom_fields(self) -> None:
        """Test create_user with custom fields."""
        user = TestDataFactory.create_user(
            username="alice",
            email="alice@example.com",
            roles=["admin", "user"],
        )

        assert user["username"] == "alice"
        assert user["email"] == "alice@example.com"
        assert user["roles"] == ["admin", "user"]

    def test_create_user_extra_kwargs_override(self) -> None:
        """Test that extra kwargs override defaults."""
        custom_time = 1234567890.0
        user = TestDataFactory.create_user(
            id="custom-id",
            created_at=custom_time,
        )

        assert user["id"] == "custom-id"
        assert user["created_at"] == custom_time

    def test_create_task_default(self) -> None:
        """Test create_task with default values."""
        task = TestDataFactory.create_task()

        assert task["id"] is not None
        assert task["name"] is not None
        assert task["status"] == "pending"
        assert task["priority"] == "normal"
        assert "created_at" in task

    def test_create_task_with_custom_id(self) -> None:
        """Test create_task with custom ID."""
        task = TestDataFactory.create_task(task_id="task-456")

        assert task["id"] == "task-456"

    def test_create_task_with_custom_fields(self) -> None:
        """Test create_task with custom fields."""
        task = TestDataFactory.create_task(
            name="Important Task",
            status="completed",
            priority="high",
        )

        assert task["name"] == "Important Task"
        assert task["status"] == "completed"
        assert task["priority"] == "high"

    def test_create_message_default(self) -> None:
        """Test create_message with default values."""
        message = TestDataFactory.create_message()

        assert message["id"] is not None
        assert message["topic"] == "test"
        assert message["payload"] == {"test": True}
        assert "timestamp" in message

    def test_create_message_with_custom_topic(self) -> None:
        """Test create_message with custom topic."""
        message = TestDataFactory.create_message(topic="custom-topic")

        assert message["topic"] == "custom-topic"

    def test_create_message_with_custom_payload(self) -> None:
        """Test create_message with custom payload."""
        payload = {"key": "value", "number": 42}
        message = TestDataFactory.create_message(payload=payload)

        assert message["payload"] == payload

    def test_create_request_default(self) -> None:
        """Test create_request with default values."""
        request = TestDataFactory.create_request()

        assert request["method"] == "GET"
        assert request["path"] == "/"
        assert request["headers"] == {}
        assert request["query_params"] == {}
        assert request["body"] is None
        assert "timestamp" in request

    def test_create_request_with_method_and_path(self) -> None:
        """Test create_request with custom method and path."""
        request = TestDataFactory.create_request(method="POST", path="/api/users")

        assert request["method"] == "POST"
        assert request["path"] == "/api/users"

    def test_create_request_with_headers_and_query(self) -> None:
        """Test create_request with headers and query params."""
        request = TestDataFactory.create_request(
            headers={"Authorization": "Bearer token"},
            query_params={"page": "1"},
        )

        assert request["headers"] == {"Authorization": "Bearer token"}
        assert request["query_params"] == {"page": "1"}

    def test_create_request_with_body(self) -> None:
        """Test create_request with body."""
        body = {"name": "test", "value": 123}
        request = TestDataFactory.create_request(body=body)

        assert request["body"] == body

    def test_factory_module_exposes_no_instance(self) -> None:
        """plans/09182026 S-03: the factory is a class, not a module global."""
        from quadkit.testing.lib import factory as factory_module

        assert not hasattr(factory_module, "test_data_factory")
        assert isinstance(TestDataFactory(), TestDataFactory)
