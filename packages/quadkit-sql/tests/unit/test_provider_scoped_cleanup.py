import pytest

from quadkit.sql.providers import DatabaseService


class BadConnCM:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        # Simulate failure during context manager exit
        raise RuntimeError("boom during __aexit__")


class FakePool:
    def __init__(self):
        self._initialized = True

    async def initialize(self):
        self._initialized = True

    def get_connection(self):
        return BadConnCM(object())

    async def return_connection(self, conn):
        # shouldn't be called in this test path
        pass


@pytest.mark.asyncio
async def test_scoped_context_cleanup_logs_and_swallows_exception():
    from unittest.mock import patch
    provider = DatabaseService(url="sqlite:///:memory:")
    await provider.boot()
    provider.connection_pool = FakePool()

    with patch("quadkit.sql.managers.manager.logger") as mock_logger:
        async with provider.scoped_context() as ctx:
            conn = await provider.get_scoped_connection()
            assert conn is not None

        # After exiting scope, ensure it was logged
        mock_logger.exception.assert_called()
        args, _ = mock_logger.exception.call_args
        assert "Error exiting connection context manager" in args[0]
