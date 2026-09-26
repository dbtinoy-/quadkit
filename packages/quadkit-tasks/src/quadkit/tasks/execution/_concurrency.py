"""Task worker lifecycle and concurrency helpers."""

from __future__ import annotations

import asyncio
import contextlib

from quadkit.concurrency.task_utils import create_tracked_task


class WorkerConcurrencyMixin:
    async def start(self) -> None:
        self.running = True
        if self._task_manager is not None:  # type: ignore[attr-defined]
            self._task = self._task_manager.create_critical_task(  # type: ignore[attr-defined]
                self._work_loop(),
                name=self.worker_id,  # type: ignore[attr-defined]
            )
        else:
            self._task = create_tracked_task(
                self._work_loop(),
                self._background_tasks,  # type: ignore[attr-defined]
                name=f"worker_loop_{self.worker_id}",  # type: ignore[attr-defined]
            )
        self.logger.info("Worker %s started", self.worker_id)  # type: ignore[attr-defined]

    async def stop(self, drain: bool = False, timeout: float | None = 30.0) -> None:
        if drain:
            self._draining = True
            self.logger.info(  # type: ignore[attr-defined]
                "Worker %s entering drain mode, waiting for in-flight jobs",
                self.worker_id,  # type: ignore[attr-defined]
            )

            if self.current_job and timeout:  # type: ignore[attr-defined]
                try:
                    await asyncio.wait_for(
                        self._wait_for_current_job(), timeout=timeout
                    )
                except TimeoutError:
                    self.logger.warning(  # type: ignore[attr-defined]
                        "Worker %s drain timeout, forcing stop with job in progress",
                        self.worker_id,  # type: ignore[attr-defined]
                    )

        self.running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self.logger.info("Worker %s stopped", self.worker_id)  # type: ignore[attr-defined]

    async def _wait_for_current_job(self) -> None:
        while self.current_job is not None:  # type: ignore[attr-defined]
            await asyncio.sleep(0.1)

    async def _work_loop(self) -> None:
        while self.running:
            if self._draining and self.current_job is None:  # type: ignore[attr-defined]
                self.logger.info(  # type: ignore[attr-defined]
                    "Worker %s drain complete, exiting work loop",
                    self.worker_id,  # type: ignore[attr-defined]
                )
                break

            try:
                task = await self.queue.dequeue()  # type: ignore[attr-defined]
                if task:
                    job = task.to_job() if hasattr(task, "to_job") else task
                    await self._execute_job(job)  # type: ignore[attr-defined]
                else:
                    await asyncio.sleep(0.5 if self._draining else 1.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # The worker loop must stay alive on unexpected handler/queue
                # failures; otherwise one surprising runtime error can kill the
                # entire worker process until an external supervisor restarts it.
                self.logger.exception("worker_loop.unexpected_error", error=str(exc))  # type: ignore[attr-defined]
                await asyncio.sleep(1)


__all__ = ["WorkerConcurrencyMixin"]
