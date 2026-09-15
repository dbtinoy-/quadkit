"""Tests for testing utilities."""

import asyncio
import importlib.util
import os

import pytest

# Import lib directly by loading the module
lib_spec = importlib.util.spec_from_file_location(
    "lib",
    os.path.join(os.path.dirname(__file__), "..", "..", "src", "quadkit", "testing", "lib", "__init__.py"),
)
lib_module = importlib.util.module_from_spec(lib_spec)
lib_spec.loader.exec_module(lib_module)

# Import live utility classes
AsyncTestHelper = lib_module.AsyncTestHelper
TestAssertions = lib_module.TestAssertions
TestDataFactory = lib_module.TestDataFactory
test_assertions = lib_module.test_assertions
test_data_factory = lib_module.test_data_factory


class TestAsyncTestHelper:
    """Test AsyncTestHelper functionality."""

    @pytest.mark.asyncio
    async def test_wait_for_condition(self):
        """Test waiting for a condition to become true."""
        condition_met = await AsyncTestHelper.wait_for_condition(lambda: True, timeout=1.0)
        assert condition_met

        condition_met = await AsyncTestHelper.wait_for_condition(lambda: False, timeout=0.1)
        assert not condition_met

    @pytest.mark.asyncio
    async def test_collect_async_results(self):
        """Test collecting results from multiple async operations."""
        async def coro(value):
            await asyncio.sleep(0.01)
            return value * 2

        coros = [coro(1), coro(2), coro(3)]
        results = await AsyncTestHelper.collect_async_results(coros)

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_run_with_timeout(self):
        """Test running coroutine with timeout."""
        async def quick_coro():
            await asyncio.sleep(0.01)
            return "success"

        async def slow_coro():
            await asyncio.sleep(1.0)
            return "too slow"

        result = await AsyncTestHelper.run_with_timeout(quick_coro(), timeout=0.1)
        assert result == "success"

        with pytest.raises(asyncio.TimeoutError):
            await AsyncTestHelper.run_with_timeout(slow_coro(), timeout=0.05)


class TestTestDataFactory:
    """Test TestDataFactory functionality."""

    def test_create_user(self):
        """Test user data creation."""
        user = TestDataFactory.create_user(user_id="user123", email="test@example.com")

        assert user["id"] == "user123"
        assert user["email"] == "test@example.com"
        assert "username" in user
        assert "roles" in user
        assert "created_at" in user

    def test_create_task(self):
        """Test task data creation."""
        task = TestDataFactory.create_task(task_id="task123", name="Test Task")

        assert task["id"] == "task123"
        assert task["name"] == "Test Task"
        assert task["status"] == "pending"
        assert "created_at" in task

    def test_create_message(self):
        """Test message data creation."""
        message = TestDataFactory.create_message(topic="test.topic", payload={"key": "value"})

        assert message["topic"] == "test.topic"
        assert message["payload"] == {"key": "value"}
        assert "id" in message
        assert "timestamp" in message

    def test_create_request(self):
        """Test HTTP request data creation."""
        request = TestDataFactory.create_request(
            method="POST",
            path="/api/users",
            headers={"Content-Type": "application/json"},
        )

        assert request["method"] == "POST"
        assert request["path"] == "/api/users"
        assert request["headers"]["Content-Type"] == "application/json"
        assert "timestamp" in request


class TestTestAssertions:
    """Test TestAssertions functionality."""

    def test_assert_dict_contains_subset(self):
        """Test dictionary subset assertion."""
        superset = {"a": 1, "b": 2, "c": 3}
        subset = {"a": 1, "c": 3}

        TestAssertions.assert_dict_contains_subset(subset, superset)

        with pytest.raises(AssertionError):
            TestAssertions.assert_dict_contains_subset({"d": 4}, superset)

        with pytest.raises(AssertionError):
            TestAssertions.assert_dict_contains_subset({"a": 999}, superset)

    @pytest.mark.asyncio
    async def test_assert_async_raises(self):
        """Test async exception assertion."""
        async def success_coro():
            return "success"

        async def failure_coro():
            raise ValueError("test error")

        await TestAssertions.assert_async_raises(ValueError, failure_coro())

        with pytest.raises(AssertionError):
            await TestAssertions.assert_async_raises(ValueError, success_coro())

        with pytest.raises(AssertionError):
            await TestAssertions.assert_async_raises(RuntimeError, failure_coro())

    def test_assert_metrics_contain(self):
        """Test metrics assertion."""
        metrics = {"response_time": 0.5, "error_rate": 0.01}

        TestAssertions.assert_metrics_contain(metrics, "response_time")
        TestAssertions.assert_metrics_contain(metrics, "response_time", min_value=0.3)

        with pytest.raises(AssertionError):
            TestAssertions.assert_metrics_contain(metrics, "nonexistent")

        with pytest.raises(AssertionError):
            TestAssertions.assert_metrics_contain(metrics, "response_time", min_value=0.8)


class TestGlobalInstances:
    """Test global utility instances."""

    def test_test_assertions_instance(self):
        """Test global test assertions."""
        assert isinstance(test_assertions, TestAssertions)

    def test_test_data_factory_instance(self):
        """Test global test data factory."""
        assert isinstance(test_data_factory, TestDataFactory)

        user = test_data_factory.create_user()
        assert "id" in user
        assert "username" in user

