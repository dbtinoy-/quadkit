"""Idempotent decorator tests."""

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


class TestIdempotentDecorator:
    """Test idempotent decorator."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_idempotency_cache()

    def test_idempotent_with_key_func(self):
        """Test idempotent decorator with custom key function."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            request_id: str
            data: str

        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def test_handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd = TestCommand(request_id="req-123", data="test")

        # First call
        result1 = test_handler(cmd)
        assert result1 == "processed: test"
        assert call_count == 1

        # Second call with same key should return cached result
        result2 = test_handler(cmd)
        assert result2 == "processed: test"
        assert call_count == 1  # Should not have been called again

    def test_idempotent_with_idempotency_key_attribute(self):
        """Test idempotent decorator using command's idempotency_key attribute."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            idempotency_key: str
            data: str

        call_count = 0

        @idempotent()
        def test_handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd = TestCommand(idempotency_key="key-123", data="test")

        # First call
        result1 = test_handler(cmd)
        assert result1 == "processed: test"
        assert call_count == 1

        # Second call with same key should return cached result
        result2 = test_handler(cmd)
        assert result2 == "processed: test"
        assert call_count == 1

    def test_idempotent_with_content_hash(self):
        """Test idempotent decorator using content hash when no key provided."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            data: str

        call_count = 0

        @idempotent()
        def test_handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd1 = TestCommand(data="test")
        cmd2 = TestCommand(data="test")  # Same content

        # First call
        result1 = test_handler(cmd1)
        assert result1 == "processed: test"
        assert call_count == 1

        # Second call with same content should return cached result
        result2 = test_handler(cmd2)
        assert result2 == "processed: test"
        assert call_count == 1

    def test_idempotent_async(self):
        """Test idempotent decorator with async function."""
        import asyncio

        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            request_id: str
            data: str

        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        async def test_handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            return f"processed: {command.data}"

        async def run_test():
            cmd = TestCommand(request_id="req-123", data="test")

            # First call
            result1 = await test_handler(cmd)
            assert result1 == "processed: test"
            assert call_count == 1

            # Second call with same key should return cached result
            result2 = await test_handler(cmd)
            assert result2 == "processed: test"
            assert call_count == 1

        asyncio.run(run_test())

    def test_idempotent_no_command(self):
        """Test idempotent decorator when no command is found."""

        @idempotent()
        def test_handler(data: str) -> str:
            return f"processed: {data}"

        result = test_handler("test")
        assert result == "processed: test"

    def test_clear_idempotency_cache(self):
        """Test clearing idempotency cache."""
        from quadkit.domain import DomainModel

        @dataclass
        class TestCommand(DomainModel):
            request_id: str
            data: str

        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def test_handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd = TestCommand(request_id="req-123", data="test")

        # First call
        test_handler(cmd)
        assert call_count == 1

        # Second call should use cache
        test_handler(cmd)
        assert call_count == 1

        # Clear cache
        clear_idempotency_cache()

        # Third call should execute again
        test_handler(cmd)
