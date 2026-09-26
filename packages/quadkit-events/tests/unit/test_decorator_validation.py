"""validate / validate_command / validate_query decorator tests."""

from __future__ import annotations

from dataclasses import dataclass

from typing import cast

import pytest

from quadkit.events.decorators.handlers import (
    HandlerInfo,
    clear_handlers,
    command_handler,
    event_handler,
    get_all_handlers,
    get_handler_info,
    multi_event_handler,
    projection,
    query_handler,
    saga,
)
from quadkit.events.decorators.validation import (
    CQRSValidationError,
    clear_idempotency_cache,
    idempotent,
    validate,
    validate_command,
    validate_query,
)
from quadkit.events.messages.command import Command
from quadkit.events.messages.event import Event
from quadkit.events.messages.query import Query


from decorator_test_support import _TestCommand, _TestEvent, _TestProjection, _TestQuery, _TestSaga


class TestValidateDecorator:
    """Test validate decorator."""

    def test_validate_sync_function_success(self):
        """Test validate decorator with sync function success."""

        @validate
        def test_func(data: str) -> str:
            return f"processed: {data}"

        result = test_func("test")
        assert result == "processed: test"

    def test_validate_async_function_success(self):
        """Test validate decorator with async function success."""
        import asyncio

        @validate
        async def test_func(data: str) -> str:
            await asyncio.sleep(0.001)
            return f"processed: {data}"

        async def run_test():
            result = await test_func("test")
            assert result == "processed: test"

        asyncio.run(run_test())

    def test_validate_sync_function_validation_error(self):
        """Test validate decorator catches validation errors."""
        from quadkit.contracts.exceptions.domain import ValidationError

        @validate
        def test_func() -> str:
            err = ValidationError("Validation failed")
            err.add_error("value", "Input should be a valid integer")
            raise err

        with pytest.raises(CQRSValidationError) as exc_info:
            test_func()

        assert "Validation failed" in str(exc_info.value)
        assert "value" in str(exc_info.value)

    def test_validate_async_function_validation_error(self):
        """Test validate decorator catches validation errors in async functions."""
        import asyncio

        from quadkit.contracts.exceptions.domain import ValidationError

        @validate
        async def test_func() -> str:
            await asyncio.sleep(0.001)
            err = ValidationError("Validation failed")
            err.add_error("value", "Input should be a valid integer")
            raise err

        async def run_test():
            with pytest.raises(CQRSValidationError) as exc_info:
                await test_func()

            assert "Validation failed" in str(exc_info.value)

        asyncio.run(run_test())


class TestValidateCommandDecorator:
    """Test validate_command decorator."""

    def test_validate_command_success(self):
        """Test validate_command decorator success."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            username: str
            email: str

        @validate_command(
            max_length={"username": 50, "email": 100},
            required_fields=["username", "email"],
        )
        def test_handler(command: TestCommand) -> str:
            return f"user: {command.username}"

        cmd = TestCommand(username="testuser", email="test@example.com")
        result = test_handler(cmd)
        assert result == "user: testuser"

    def test_validate_command_required_field_missing(self):
        """Test validate_command with missing required field."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            username: str
            email: str

        @validate_command(required_fields=["username", "email"])
        def test_handler(command: TestCommand) -> str:
            return f"user: {command.username}"

        cmd = TestCommand(username="", email="test@example.com")

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(cmd)

        assert "required" in str(exc_info.value).lower()

    def test_validate_command_max_length_exceeded(self):
        """Test validate_command with max length exceeded."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            username: str
            email: str

        @validate_command(max_length={"username": 5})
        def test_handler(command: TestCommand) -> str:
            return f"user: {command.username}"

        cmd = TestCommand(username="verylongusername", email="test@example.com")

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(cmd)

        assert "exceeds maximum length" in str(exc_info.value)

    def test_validate_command_custom_validator(self):
        """Test validate_command with custom validator."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            username: str
            email: str

        def custom_validator(command):
            if "@" not in command.email:
                raise ValueError("Invalid email format")

        @validate_command(custom_validators=[custom_validator])
        def test_handler(command: TestCommand) -> str:
            return f"user: {command.username}"

        cmd = TestCommand(username="testuser", email="invalidemail")

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(cmd)

        assert "Invalid email format" in str(exc_info.value)

    def test_validate_command_async(self):
        """Test validate_command decorator with async function."""
        import asyncio

        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            username: str

        @validate_command(required_fields=["username"])
        async def test_handler(command: TestCommand) -> str:
            await asyncio.sleep(0.001)
            return f"user: {command.username}"

        async def run_test():
            cmd = TestCommand(username="testuser")
            result = await test_handler(cmd)
            assert result == "user: testuser"

        asyncio.run(run_test())


class TestValidateQueryDecorator:
    """Test validate_query decorator."""

    def test_validate_query_success(self):
        """Test validate_query decorator success."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestQuery(DomainModel):
            limit: int = 10
            sort_by: str = "created_at"

        @validate_query(max_results=100, allowed_sort_fields=["created_at", "name"])
        def test_handler(query: TestQuery) -> str:
            return f"limit: {query.limit}, sort: {query.sort_by}"

        query = TestQuery(limit=50, sort_by="name")
        result = test_handler(query)
        assert result == "limit: 50, sort: name"

    def test_validate_query_max_results_exceeded(self):
        """Test validate_query with max results exceeded."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestQuery(DomainModel):
            limit: int = 10

        @validate_query(max_results=100)
        def test_handler(query: TestQuery) -> str:
            return f"limit: {query.limit}"

        query = TestQuery(limit=150)

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(query)

        assert "exceeds maximum" in str(exc_info.value)

    def test_validate_query_invalid_sort_field(self):
        """Test validate_query with invalid sort field."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestQuery(DomainModel):
            sort_by: str = "created_at"

        @validate_query(allowed_sort_fields=["created_at", "name"])
        def test_handler(query: TestQuery) -> str:
            return f"sort: {query.sort_by}"

        query = TestQuery(sort_by="invalid_field")

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(query)

        assert "not allowed" in str(exc_info.value)

    def test_validate_query_page_size(self):
        """Test validate_query with page_size field."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestQuery(DomainModel):
            page_size: int = 10

        @validate_query(max_results=50)
        def test_handler(query: TestQuery) -> str:
            return f"page_size: {query.page_size}"

        query = TestQuery(page_size=60)

        with pytest.raises(CQRSValidationError) as exc_info:
            test_handler(query)

        assert "exceeds maximum" in str(exc_info.value)

    def test_validate_query_async(self):
        """Test validate_query decorator with async function."""
        import asyncio

        from quadkit.domain import DomainModel

        @dataclass
        class TestQuery(DomainModel):
            limit: int = 10

        @validate_query(max_results=100)
        async def test_handler(query: TestQuery) -> str:
            await asyncio.sleep(0.001)
            return f"limit: {query.limit}"

        async def run_test():
            query = TestQuery(limit=50)
            result = await test_handler(query)
            assert result == "limit: 50"

        asyncio.run(run_test())


