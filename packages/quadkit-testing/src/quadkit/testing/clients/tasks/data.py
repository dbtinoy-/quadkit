"""Sample data factories for task testing.

Provides :class:`TaskTestData` with static helpers that return representative
task/job dictionaries for use in unit and integration tests.
"""

from __future__ import annotations

from typing import Any


class TaskTestData:
    """Static collection of canned task/job fixtures for testing.

    All methods return plain :class:`dict` objects so that callers can use
    them without importing task-specific model classes.  The dicts are
    intentionally simple and cover the same task names that
    :class:`~quadkit.testing.clients.tasks.MockTaskExecutor` recognises.
    """

    @staticmethod
    def sample_tasks() -> list[dict[str, Any]]:
        """Return three representative task definitions.

        Returns:
            A list of three task dicts covering email_notification,
            data_processing, and cleanup_job.
        """
        return [
            {
                "name": "email_notification",
                "args": ("user@example.com", "Hello from tests"),
                "kwargs": {},
            },
            {
                "name": "data_processing",
                "args": ([1, 2, 3],),
                "kwargs": {"operation": "sum"},
            },
            {
                "name": "cleanup_job",
                "args": (),
                "kwargs": {},
            },
        ]

    @staticmethod
    def sample_jobs() -> list[dict[str, Any]]:
        """Return two representative background-job definitions.

        Returns:
            A list with batch_import and maintenance dicts.
        """
        return [
            {
                "name": "batch_import",
                "args": (),
                "kwargs": {"source": "test_data.csv"},
            },
            {
                "name": "maintenance",
                "args": (),
                "kwargs": {"target": "old_records"},
            },
        ]

    @staticmethod
    def sample_scheduled_jobs() -> list[dict[str, Any]]:
        """Return two scheduled-job definitions.

        Returns:
            A list with daily_backup and hourly_cleanup dicts.
        """
        return [
            {
                "name": "daily_backup",
                "schedule": "0 0 * * *",
                "kwargs": {},
            },
            {
                "name": "hourly_cleanup",
                "schedule": "0 * * * *",
                "kwargs": {},
            },
        ]


__all__ = ["TaskTestData"]
