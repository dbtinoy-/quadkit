# Quadkit Core Testing Module

The `quadkit.testing` module provides comprehensive testing infrastructure for the entire Quadkit Framework, enabling developers to write robust, maintainable tests across all packages.

## Overview

This module offers:
- **Mock Providers** for all Quadkit packages
- **Test Infrastructure** (TestBed, fixtures)
- **Context Mocking** for quadkit Context integration
- **Testing Utilities** (async helpers, data factories, assertions)
- **Specialized Helpers** (HTTP, database, events, security, etc.)

## Quick Start

```python
from quadkit.testing import TestBed, MockDatabaseProvider, MockCacheProvider


async def test_my_feature():
    # Create test bed with mock providers
    bed = TestBed()
    bed.use_provider(MockDatabaseProvider())
    bed.use_provider(MockCacheProvider())

    async with bed.context():
        # Test your code
        db = bed.container.resolve(DatabaseService)
        cache = bed.container.resolve(CacheService)

        # Your test logic here
        assert await db.health_check()
        assert await cache.health_check()
```

## Core Components

### TestBed

The `TestBed` provides isolated testing environments with dependency injection.

```python
from quadkit.testing import TestBed, create_test_bed

# Create a test bed
bed = TestBed("my-test")

# Add providers
bed.use_provider(MockDatabaseProvider())

# Use context manager
async with bed.context():
    service = bed.resolve(MyService)
    # Test service
```

### Mock Providers

Mock implementations for all Quadkit packages:

```python
from quadkit.testing import (
    MockWebProvider,
    MockTaskProvider,
    MockMessagingProvider,
    MockGraphQLProvider,
    MockMonitorProvider,
    MockEventsProvider,
    MockConnectProvider,
    MockIntelligenceProvider,
    MockSearchProvider,
)

# Create specialized mocks
web_mock = MockWebProvider(routes={"/api": lambda: {"status": 200}})
task_mock = MockTaskProvider()
```

## Context Mocking

Mock quadkit Context for request-scoped testing:

```python
from quadkit.testing import mock_context


async def test_with_context():
    ctx = mock_context()

    # Set context values
    ctx.set("user_id", "123")
    ctx.set("request_id", "req-456")

    # Use in scoped context
    async with ctx.scope(tenant_id="tenant-789"):
        assert ctx.get("user_id") == "123"
        assert ctx.get("tenant_id") == "tenant-789"

    # Context cleared after scope
    assert ctx.get("tenant_id") is None
```

## Testing Utilities

### Async Testing Helpers

```python
from quadkit.testing import AsyncTestHelper

# Wait for condition
await AsyncTestHelper.wait_for_condition(lambda: some_condition(), timeout=5.0)

# Run with timeout
result = await AsyncTestHelper.run_with_timeout(some_async_func(), timeout=10.0)
```

### Test Data Factories

```python
from quadkit.testing import test_data_factory

# Generate test data
user = test_data_factory.create_user(username="testuser", email="test@example.com")
task = test_data_factory.create_task(name="Test Task", priority="high")
message = test_data_factory.create_message("user.created", {"user_id": "123"})
```

### Custom Assertions

```python
from quadkit.testing import test_assertions

# Assert eventual condition
test_assertions.assert_eventually_true(lambda: service.is_ready(), timeout=5.0)

# Assert async exception
await test_assertions.assert_async_raises(ValueError, failing_async_func())
```

### Performance Testing

```python
from quadkit.testing import performance_tester

# Benchmark function
result = await performance_tester.benchmark_async(my_async_func, iterations=100)
print(f"Avg time: {result['avg_time']:.4f}s, Ops/sec: {result['ops_per_sec']:.2f}")
```

## Specialized Helpers

### HTTP Testing

```python
from quadkit.testing import HTTPTestingHelper

# Create mock request/response
request = HTTPTestingHelper.create_mock_request(
    "POST", "/api/users", body='{"name": "John"}'
)
response = HTTPTestingHelper.create_mock_response(201, json_data={"id": 123})

# Assert response
HTTPTestingHelper.assert_http_response(response, 201, {"id": 123})
```

### Database Testing

```python
from quadkit.testing import DatabaseTestingHelper

# Create mock query result
result = DatabaseTestingHelper.create_mock_query_result(
    [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]
)

# Assert result
DatabaseTestingHelper.assert_query_result(result, expect_success=True)
```

### Event Testing

```python
from quadkit.testing import EventTestingHelper

# Create mock event
event = EventTestingHelper.create_mock_event("user.created", {"user_id": "123"})

# Create handler tracker
tracker = EventTestingHelper.create_event_handler_tracker()
await tracker["handler"](event)

# Assert handling
EventTestingHelper.assert_event_handled(
    tracker, expected_count=1, event_type="user.created"
)
```

### Security Testing

```python
from quadkit.testing import SecurityTestingHelper

# Create mock JWT
token = SecurityTestingHelper.create_mock_jwt_token(user_id="123", roles=["admin"])

# Create permissions
perms = SecurityTestingHelper.create_mock_permissions(["read", "write"])

# Assert permissions
SecurityTestingHelper.assert_permission_granted(["read", "write"], "read")
```

### Configuration Testing

```python
from quadkit.testing import ConfigurationTestingHelper

# Create nested config
config = ConfigurationTestingHelper.create_nested_config(
    "database.host", "localhost", "database.port", 5432, "cache.ttl", 300
)

# Assert config values
ConfigurationTestingHelper.assert_config_value(config, "database.host", "localhost")
```

## Pytest Integration

All components work seamlessly with pytest:

```python
import pytest
from quadkit.testing import test_bed, mock_db, mock_cache, test_context


@pytest.mark.asyncio
async def test_my_service(test_bed, mock_db, mock_cache, test_context):
    # Setup context
    test_context.set("user_id", "123")

    # Configure test bed
    test_bed.use_provider(mock_db)
    test_bed.use_provider(mock_cache)

    async with test_bed.context():
        service = test_bed.resolve(MyService)
        result = await service.do_something()

        assert result is not None
```

## Best Practices

### Test Organization

```python
from quadkit.testing import TestOrganizer

@TestOrganizer.mark_slow
async def test_slow_operation():
    # Slow test implementation

@TestOrganizer.mark_integration
async def test_external_service():
    # Integration test implementation
```

### Error Testing

```python
from quadkit.testing import ErrorTestingHelper

# Test retry scenarios
retry_func = ErrorTestingHelper.create_retry_scenario(
    attempts=3, success_on_attempt=3, exception_class=ConnectionError
)

# Should fail twice, succeed on third try
result = await retry_func()  # Raises ConnectionError
result = await retry_func()  # Raises ConnectionError
result = await retry_func()  # Returns "Success on attempt 3"
```

### Data Validation

```python
from quadkit.testing import DataValidationHelper

# Validate against Pydantic model
errors = DataValidationHelper.validate_pydantic_model(UserModel, {"name": "John"})
assert len(errors) == 0

# Compare data structures
diffs = DataValidationHelper.compare_data_structures(actual_data, expected_data)
assert len(diffs) == 0
```

## Integration Testing

```python
from quadkit.testing import IntegrationTester


async def test_multi_provider_integration():
    tester = IntegrationTester()

    # Add multiple providers
    tester.add_provider(MockDatabaseProvider())
    tester.add_provider(MockCacheProvider())
    tester.add_provider(MockMessagingProvider())

    # Setup integration
    results = await tester.setup_integration()

    # All providers should be healthy
    for name, result in results.items():
        assert result["status"] == "started"

    # Run integration tests
    # ... your integration logic ...

    # Teardown
    await tester.teardown_integration()
```

## Contributing

When adding new mock providers or utilities:

1. Follow the naming convention: `Mock{Package}Provider`
2. Include comprehensive health checks
3. Add appropriate factory functions
4. Update pytest fixtures
5. Add documentation and examples
6. Include unit tests for the testing utilities themselves

This testing module ensures consistent, reliable testing across the entire Quadkit Framework ecosystem.
