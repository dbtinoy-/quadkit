"""Test configuration and fixtures."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

# Monkeypatch httpx.Client to support 'app' argument from Starlette 0.27.0
# TestClient when using httpx 0.28.0+ which removed it from __init__.
_original_httpx_client_init = httpx.Client.__init__


def _fixed_httpx_client_init(self, *args, **kwargs):
    if "app" in kwargs:
        app = kwargs.pop("app")
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.ASGITransport(app=app)
    _original_httpx_client_init(self, *args, **kwargs)


httpx.Client.__init__ = _fixed_httpx_client_init

# Import from the consolidated testing package
from quadkit.testing.fixtures.bed import TestEnvironment

# Load core testing fixtures
try:
    import importlib

    importlib.import_module("quadkit.testing.fixtures.core")
    importlib.import_module("quadkit.testing.fixtures.web")
    from quadkit.testing.fixtures.web import (
        mock_web_request,  # noqa: F401
        mock_web_response,  # noqa: F401
        sample_web_post_data,  # noqa: F401
        sample_web_user_data,  # noqa: F401
        web_test_bed,  # noqa: F401
        web_test_client,  # noqa: F401
    )
except ImportError:
    pass


@pytest.fixture(autouse=True)
def reset_web_registries() -> None:
    """Prevent test pollution from shared pipeline state.

    plans/09172026 H-04 removed the module-level route/controller registry
    globals (registries are per-application instances now), so only the
    process-global filter pipeline still needs resetting between tests.
    """
    yield
    from quadkit.web.filters.pipeline import filter_pipeline

    filter_pipeline.clear()


@pytest.fixture
def app():
    """Returns a fresh Application instance for every test."""
    from quadkit.app import Application

    return Application()


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed(app):
    """Returns a TestBed with in-memory drivers pre-configured."""
    from quadkit.identity.di.provider import IdentityProvider
    from quadkit.observability.di.sub_providers.observability import (
        ObservabilityProvider,
    )
    from quadkit.web.config import RateLimitConfig, WebConfig
    from quadkit.web.di.provider import WebProvider

    # Disable rate limiting for tests to avoid dependency on RateLimitProvider
    rate_limit_config = RateLimitConfig(enabled=False)
    # Enable debug routes for tests that need them
    web_config = WebConfig(rate_limit=rate_limit_config, debug_routes=True)
    bed = TestEnvironment(app)

    # Add core infrastructure providers first (web depends on them)
    bed.use_provider(IdentityProvider())
    bed.use_provider(ObservabilityProvider())

    # Auth callback that always allows access for tests
    async def always_allow_auth(request: Any) -> bool:
        return True

    # Add WebProvider to make web services available
    # Pass auth callback to allow debug routes in tests
    bed.use_provider(
        WebProvider(web_config=web_config, debug_routes_auth=always_allow_auth)
    )
    async with bed.context():
        yield bed


class MockRedis:
    """Mock Redis client for testing."""

    def __init__(self):
        self.data = {}

    async def ping(self):
        """Mock ping command."""
        return "PONG"

    async def info(self, section):
        """Mock info command."""
        if section == "memory":
            return {
                "used_memory": 1024 * 1024 * 50,  # 50MB
                "maxmemory": 1024 * 1024 * 100,  # 100MB
            }
        return {}

    async def eval(self, script, keys, args):
        """Mock eval for Lua scripts."""
        # Simple mock implementation for rate limiting script
        key = keys[0]
        now = float(args[0])
        window_start = float(args[1])
        max_requests = int(args[2])
        window_seconds = float(args[3])

        # Get current data for key
        if key not in self.data:
            self.data[key] = []

        # Remove old entries
        self.data[key] = [entry for entry in self.data[key] if entry[0] >= window_start]

        # Count current entries
        current_count = len(self.data[key])

        if current_count < max_requests:
            # Add new entry
            self.data[key].append((now, now))
            remaining = max_requests - current_count - 1
            return [1, remaining]

        # Rate limit exceeded
        oldest = min(self.data[key], key=lambda x: x[0])
        retry_after = int(oldest[0] + window_seconds - now)
        return [0, retry_after]

    async def zadd(self, key, mapping):
        """Mock zadd."""
        if key not in self.data:
            self.data[key] = []
        for score, member in mapping.items():
            self.data[key].append((score, member))

    async def zremrangebyscore(self, key, min_score, max_score):
        """Mock zremrangebyscore."""
        if key in self.data:
            self.data[key] = [
                entry
                for entry in self.data[key]
                if not (min_score <= entry[0] <= max_score)
            ]

    async def zcard(self, key):
        """Mock zcard."""
        return len(self.data.get(key, []))

    async def zrange(self, key, start, end, withscores=False):
        """Mock zrange."""
        data = self.data.get(key, [])
        sorted_data = sorted(data, key=lambda x: x[0])
        result = sorted_data[start : end + 1]
        if withscores:
            return result
        return [item[1] for item in result]

    async def expire(self, key, seconds):
        """Mock expire - no-op for testing."""


@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def redis_client():
    """Mock Redis client for testing."""
    return MockRedis()
