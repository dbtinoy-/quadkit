"""Tests for RunnableLambda."""
from __future__ import annotations

import pytest

from quadkit.result import Err


class TestRunnableLambda:
    """Tests for RunnableLambda."""

    def test_sync_lambda_invoke(self) -> None:
        """Sync lambda should work with invoke."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        runnable = RunnableLambda(lambda x: x.upper())
        result = runnable.invoke("hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_sync_lambda_ainvoke(self) -> None:
        """Sync lambda should work with ainvoke."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        runnable = RunnableLambda(lambda x: x.upper())
        result = await runnable.ainvoke("hello")
        assert result == "HELLO"

    @pytest.mark.asyncio
    async def test_async_lambda_ainvoke(self) -> None:
        """Async lambda should work with ainvoke."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        async def async_upper(x: str) -> str:
            return x.upper()

        runnable = RunnableLambda(async_upper)
        result = await runnable.ainvoke("hello")
        assert result == "HELLO"

    def test_sync_lambda_ainvoke_works(self) -> None:
        """Sync lambda should work with ainvoke (just calls the func)."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        runnable = RunnableLambda(lambda x: x.upper())
        result = runnable.ainvoke("hello")
        import asyncio
        ret = asyncio.run(result)
        assert ret == "HELLO"

    def test_lambda_catches_exception(self) -> None:
        """Lambda should catch exceptions and return Err."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        runnable = RunnableLambda(lambda x: x.upper())
        result = runnable.invoke(123)
        assert isinstance(result, Err)

    @pytest.mark.asyncio
    async def test_lambda_errors_are_sanitized_in_results_and_logs(self, capsys) -> None:
        """Sync and async failures omit raw exception text."""
        from quadkit.ai.llm.runnable.lambda_ import RunnableLambda

        secret = "RUNNABLE_LAMBDA_SECRET_SENTINEL"

        def fail_sync(_: str) -> str:
            raise RuntimeError(secret)

        sync_result = RunnableLambda(fail_sync).invoke("input")
        assert isinstance(sync_result, Err)
        sync_error = sync_result.unwrap_err()
        assert sync_error.message == "Lambda execution failed"
        assert sync_error.details == {"error_type": "RuntimeError"}
        assert secret not in str(sync_error)
        assert secret not in repr(sync_error.to_dict())

        async def fail_async(_: str) -> str:
            raise RuntimeError(secret)

        async_result = await RunnableLambda(fail_async).ainvoke("input")
        assert isinstance(async_result, Err)
        async_error = async_result.unwrap_err()
        assert async_error.message == "Lambda execution failed"
        assert async_error.details == {"error_type": "RuntimeError"}
        assert secret not in str(async_error)
        assert secret not in repr(async_error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
