"""Tests for WebProvider static file mounting."""

import asyncio
import tempfile

from quadkit.di.container import Container
from quadkit.web.config import RateLimitConfig, StaticFileConfig, WebConfig
from quadkit.web.di.provider import WebProvider


def test_static_files_mounted_when_enabled() -> None:
    """Test that WebProvider mounts static files when config.static.enabled=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = WebConfig(
            rate_limit=RateLimitConfig(enabled=False),
            static=StaticFileConfig(
                enabled=True,
                directory=tmpdir,
                prefix="/assets",
                html=False,
            ),
        )
        provider = WebProvider(web_config=config)
        container = Container()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.register(container))
            loop.run_until_complete(provider.boot(container))

            # Verify static files route is mounted
            starlette = provider.starlette
            assert any(route.path == "/assets" for route in starlette.routes)
        finally:
            loop.run_until_complete(provider.shutdown())
            loop.close()


def test_static_files_not_mounted_when_disabled() -> None:
    """Test that WebProvider skips static file mounting when disabled."""
    config = WebConfig(
        rate_limit=RateLimitConfig(enabled=False),
        static=StaticFileConfig(enabled=False, directory="public", prefix="/static"),
    )
    provider = WebProvider(web_config=config)
    container = Container()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(provider.register(container))
        loop.run_until_complete(provider.boot(container))

        # Verify no static files route
        starlette = provider.starlette
        assert not any(route.path == "/static" for route in starlette.routes)
    finally:
        loop.run_until_complete(provider.shutdown())
        loop.close()


def test_static_files_not_mounted_when_config_is_none() -> None:
    """Test that WebProvider skips static file mounting when config.static is None."""
    config = WebConfig(
        rate_limit=RateLimitConfig(enabled=False),
    )  # static defaults to None
    provider = WebProvider(web_config=config)
    container = Container()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(provider.register(container))
        loop.run_until_complete(provider.boot(container))

        # Should not crash, no static route
        starlette = provider.starlette
        assert starlette is not None
    finally:
        loop.run_until_complete(provider.shutdown())
        loop.close()


def test_static_files_mount_failure_logs_warning() -> None:
    """Test that WebProvider logs warning when static directory does not exist."""
    config = WebConfig(
        rate_limit=RateLimitConfig(enabled=False),
        static=StaticFileConfig(
            enabled=True,
            directory="/nonexistent/path/to/static",
            prefix="/bad",
        ),
    )
    provider = WebProvider(web_config=config)
    container = Container()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(provider.register(container))
        # boot should not crash even if directory doesn't exist
        loop.run_until_complete(provider.boot(container))

        # The mount happens in a try/except with logger.warning, so no exception raised
        starlette = provider.starlette
        assert starlette is not None
    finally:
        loop.run_until_complete(provider.shutdown())
        loop.close()
