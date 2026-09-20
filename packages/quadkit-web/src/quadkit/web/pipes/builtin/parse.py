"""Parse pipes for type conversion.

Pipes that parse string values into specific types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from quadkit.web.protocols import ParamMetadata, PipeProtocol


class ParseIntPipe(PipeProtocol):
    """PipeProtocol that parses string values to integers.

    Example:
        ```python
        class UserController(Controller):
            @get("/users/{user_id}")
            async def get_user(self, @path(pipe=ParseIntPipe()) user_id: int):
                ...
        ```
    """

    def __init__(self, strict: bool = True):
        """Initialize the pipe.

        Args:
            strict: If True, raises error on invalid input. If False, returns default.
        """
        self._strict = strict

    async def transform(self, value: Any, metadata: ParamMetadata) -> int:
        """Parse value to integer.

        Args:
            value: The value to parse.
            metadata: Metadata about the parameter.

        Returns:
            Parsed integer.

        Raises:
            ValueError: If strict=True and value cannot be parsed.
        """
        if value is None:
            if metadata.default is not None:
                return int(metadata.default)
            if self._strict:
                raise ValueError(f"Missing required parameter: {metadata.name}")
            return 0

        try:
            return int(value)
        except (ValueError, TypeError) as e:
            if self._strict:
                raise ValueError(f"Invalid integer for {metadata.name}: {value}") from e
            return int(metadata.default) if metadata.default is not None else 0


class ParseUUIDPipe(PipeProtocol):
    """PipeProtocol that parses string values to UUIDs.

    Example:
        ```python
        class UserController(Controller):
            @get("/users/{user_id}")
            async def get_user(self, @path(pipe=ParseUUIDPipe()) user_id: uuid.UUID):
                ...
        ```
    """

    async def transform(self, value: Any, metadata: ParamMetadata) -> uuid.UUID:
        """Parse value to UUID.

        Args:
            value: The value to parse.
            metadata: Metadata about the parameter.

        Returns:
            Parsed UUID.

        Raises:
            ValueError: If value cannot be parsed as UUID.
        """
        if value is None:
            if metadata.default is not None:
                return uuid.UUID(str(metadata.default))
            raise ValueError(f"Missing required parameter: {metadata.name}")

        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid UUID for {metadata.name}: {value}") from e


class ParseBoolPipe(PipeProtocol):
    """PipeProtocol that parses string values to booleans.

    Accepts: "true", "false", "1", "0", "yes", "no"

    Example:
        ```python
        class UserController(Controller):
            @get("/users")
            async def list_users(self, @query(pipe=ParseBoolPipe()) active: bool = True):
                ...
        ```
    """

    TRUE_VALUES = {"true", "1", "yes", "on"}
    FALSE_VALUES = {"false", "0", "no", "off"}

    async def transform(self, value: Any, metadata: ParamMetadata) -> bool:
        """Parse value to boolean.

        Args:
            value: The value to parse.
            metadata: Metadata about the parameter.

        Returns:
            Parsed boolean.
        """
        if value is None:
            return metadata.default if metadata.default is not None else True

        if isinstance(value, bool):
            return value

        str_value = str(value).lower().strip()

        if str_value in self.TRUE_VALUES:
            return True
        if str_value in self.FALSE_VALUES:
            return False

        # Default for ambiguous values
        return bool(metadata.default)


class ParseDatePipe(PipeProtocol):
    """PipeProtocol that parses string values to dates/datetimes.

    Example:
        ```python
        class ReportController(Controller):
            @get("/reports")
            async def get_reports(
                self,
                @query(pipe=ParseDatePipe()) start_date: datetime
            ):
                ...
        ```
    """

    async def transform(self, value: Any, metadata: ParamMetadata) -> datetime:
        """Parse value to datetime.

        Args:
            value: The value to parse.
            metadata: Metadata about the parameter.

        Returns:
            Parsed datetime.

        Raises:
            ValueError: If value cannot be parsed as date.
        """
        if value is None:
            if metadata.default is not None:
                default = metadata.default
                if isinstance(default, datetime):
                    return default
                return datetime.fromisoformat(str(default))
            raise ValueError(f"Missing required parameter: {metadata.name}")

        if isinstance(value, datetime):
            return value

        # Try ISO format first
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            pass

        # Try other common formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue

        raise ValueError(f"Invalid date for {metadata.name}: {value}")


class DefaultValuePipe(PipeProtocol):
    """PipeProtocol that applies default values to missing parameters.

    Example:
        ```python
        class SearchController(Controller):
            @get("/search")
            async def search(
                self,
                @query(pipe=DefaultValuePipe(default="")) query: str,
                @query(pipe=DefaultValuePipe(default=10)) limit: int,
            ):
                ...
        ```
    """

    def __init__(self, default: Any = None):
        """Initialize with default value.

        Args:
            default: The default value to apply.
        """
        self._default = default

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Apply default value.

        Args:
            value: The value to check.
            metadata: Metadata about the parameter.

        Returns:
            Value or default.
        """
        if value is None:
            return self._default
        return value


__all__ = [
    "DefaultValuePipe",
    "ParseBoolPipe",
    "ParseDatePipe",
    "ParseIntPipe",
    "ParseUUIDPipe",
]
