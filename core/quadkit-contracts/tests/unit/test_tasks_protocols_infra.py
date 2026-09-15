"""Queue, provider, worker, and DLQ protocol tests."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.infra.tasks.protocols import (
    DLQProtocol,
    JobProtocol,
    JobTemplateProtocol,
    TaskExecutorProtocol,
    TaskProviderProtocol,
    TaskQueueProtocol,
    TaskWorkerProtocol,
)



class TestJobTemplateProtocol:
    """Tests for JobTemplateProtocol."""

    def test_has_required_attributes(self) -> None:
        """Test protocol has required attributes."""

        class Template:
            name: str = "test-job"
            args: tuple = ()
            kwargs: dict = {}
            priority: int = 0
            max_retries: int = 3
            timeout: float | None = None
            depends_on: list = []

        template = Template()
        assert template.name == "test-job"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Template:
            name: str = ""
            args: tuple = ()
            kwargs: dict = {}
            priority: int = 0
            max_retries: int = 0
            timeout: float | None = None
            depends_on: list = []

        assert isinstance(Template(), JobTemplateProtocol)


class TestTaskWorkerProtocol:
    """Tests for TaskWorkerProtocol."""

    @pytest.mark.asyncio
    async def test_has_start_method(self) -> None:
        """Test protocol has start async method."""

        class Worker:
            def __init__(
                self,
                worker_id: str,
                queue: Any,
                handler_registry: dict[str, Any],
            ) -> None:
                pass

            async def start(self) -> None:
                pass

        worker = Worker("worker-1", {}, {})
        await worker.start()

    @pytest.mark.asyncio
    async def test_has_stop_method(self) -> None:
        """Test protocol has stop async method."""

        class Worker:
            def __init__(
                self,
                worker_id: str,
                queue: Any,
                handler_registry: dict[str, Any],
            ) -> None:
                pass

            async def stop(self) -> None:
                pass

        worker = Worker("worker-1", {}, {})
        await worker.stop()

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Worker:
            def __init__(
                self,
                worker_id: str,
                queue: Any,
                handler_registry: dict[str, Any],
            ) -> None:
                pass

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        assert isinstance(Worker("worker-1", {}, {}), TaskWorkerProtocol)


class TestDLQProtocol:
    """Tests for DLQProtocol."""

    @pytest.mark.asyncio
    async def test_has_add_method(self) -> None:
        """Test protocol has add async method."""

        class DLQ:
            async def add(
                self,
                message_id: str,
                payload: Any,
                reason: str,
                metadata: dict[str, Any] | None = None,
            ) -> None:
                pass

        dlq = DLQ()
        await dlq.add("msg-1", {}, "error")

    @pytest.mark.asyncio
    async def test_has_get_method(self) -> None:
        """Test protocol has get async method."""

        class DLQ:
            async def get(self, message_id: str) -> dict[str, Any] | None:
                return {"id": message_id}

        dlq = DLQ()
        result = await dlq.get("msg-1")
        assert result["id"] == "msg-1"

    @pytest.mark.asyncio
    async def test_has_retry_method(self) -> None:
        """Test protocol has retry async method."""

        class DLQ:
            async def retry(self, message_id: str) -> bool:
                return True

        dlq = DLQ()
        result = await dlq.retry("msg-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_purge_method(self) -> None:
        """Test protocol has purge async method."""

        class DLQ:
            async def purge(self, message_id: str) -> bool:
                return True

        dlq = DLQ()
        result = await dlq.purge("msg-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_clear_method(self) -> None:
        """Test protocol has clear async method."""

        class DLQ:
            async def clear(self) -> int:
                return 5

        dlq = DLQ()
        result = await dlq.clear()
        assert result == 5

    @pytest.mark.asyncio
    async def test_has_size_method(self) -> None:
        """Test protocol has size async method."""

        class DLQ:
            async def size(self) -> int:
                return 10

        dlq = DLQ()
        result = await dlq.size()
        assert result == 10

    @pytest.mark.asyncio
    async def test_has_list_failed_method(self) -> None:
        """Test protocol has list_failed async method."""

        class DLQ:
            async def list_failed(
                self,
                limit: int = 100,
                offset: int = 0,
            ) -> list[dict[str, Any]]:
                return []

        dlq = DLQ()
        result = await dlq.list_failed()
        assert isinstance(result, list)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class DLQ:
            async def add(
                self,
                message_id: str,
                payload: Any,
                reason: str,
                metadata: dict | None = None,
            ) -> None:
                pass

            async def get(self, message_id: str) -> dict | None:
                return None

            async def retry(self, message_id: str) -> bool:
                return False

            async def purge(self, message_id: str) -> bool:
                return False

            async def clear(self) -> int:
                return 0

            async def size(self) -> int:
                return 0

            async def list_failed(self, limit: int = 100, offset: int = 0) -> list:
                return []

        assert isinstance(DLQ(), DLQProtocol)
