"""Inbox configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field

_INBOX_ENV_PREFIX = "QK_NOTIFICATION__INBOX__"
_INBOX_ENV_NESTED_DELIMITER = "__"


@dataclass(init=False)
class InboxConfig(BaseConfig):
    """Top-level inbox configuration.

    Loaded from the ``inbox:`` key in application.yaml, with environment
    variable overrides via ``QK_NOTIFICATION__INBOX__*`` prefix.

    Attributes:
        store_backend: Storage backend to use. One of ``'database'`` or
            ``'memory'``. Defaults to ``'database'``.
        max_page_size: Maximum number of messages returned per page.
        retention_days: Number of days to retain inbox messages before
            they are eligible for pruning.
        mark_read_on_fetch: When ``True`` messages are automatically marked
            as read when fetched via :meth:`~InboxService.get_inbox`.
    """

    config_section: ClassVar[str] = "inbox"

    model_config: ClassVar[ConfigDict] = ConfigDict(  # type: ignore[typeddict-unknown-key]
        env_prefix=_INBOX_ENV_PREFIX,
        env_nested_delimiter=_INBOX_ENV_NESTED_DELIMITER,
        extra="ignore",
    )

    store_backend: str = Field(
        default="database",
        description="Storage backend. One of 'database' or 'memory'.",
    )
    max_page_size: int = Field(
        default=50,
        ge=1,
        description="Maximum messages returned per page.",
    )
    retention_days: int = Field(
        default=30,
        ge=1,
        description="Days to retain inbox messages before pruning.",
    )
    mark_read_on_fetch: bool = Field(
        default=False,
        description="Automatically mark messages as read when fetched.",
    )


__all__ = [
    "InboxConfig",
]
