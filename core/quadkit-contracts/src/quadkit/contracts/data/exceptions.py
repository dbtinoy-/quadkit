"""Exceptions for the data access layer contracts."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.contracts.exceptions.domain import DomainError


class UnitOfWorkError(QuadkitError):
    """Raised when a unit-of-work operation fails or is used incorrectly."""

    _code = "QK_ERR_DB_006"

    def __init__(self, message: str = "Unit of work error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class DataError(DomainError):
    """Base exception for all data-domain errors.

    This is an expected, recoverable error that data clients should
    handle gracefully (e.g., retry, return not found, etc.).
    """

    _code = "QK_ERR_DB_007"

    def __init__(self, message: str = "Data error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class DataNotFoundError(DataError):
    """Raised when data item is not found."""

    _code = "QK_ERR_DB_008"

    def __init__(self, item_type: str, item_id: str, **kwargs: Any) -> None:
        self.item_type = item_type
        self.item_id = item_id
        message = f"{item_type} {item_id} not found"
        super().__init__(message, **kwargs)


class DataValidationError(DataError):
    """Raised when data validation fails."""

    _code = "QK_ERR_DB_009"

    def __init__(
        self,
        message: str,
        field: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.message = message
        self.field = field
        full_msg = f"{message}" if not field else f"{message} (field: {field})"
        super().__init__(full_msg, **kwargs)


__all__ = ["DataError", "DataNotFoundError", "DataValidationError", "UnitOfWorkError"]
