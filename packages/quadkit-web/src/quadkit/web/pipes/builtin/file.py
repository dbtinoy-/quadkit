"""File validation pipes for file uploads.

Pipes that validate file uploads (size, type, etc).
"""

from __future__ import annotations

from typing import Any

from quadkit.web.protocols import ParamMetadata, PipeProtocol


class FileSizeValidationPipe(PipeProtocol):
    """PipeProtocol that validates file upload size.

    Example:
        ```python
        class UploadController(Controller):
            @post("/upload")
            async def upload(
                self,
                @file(pipe=FileSizeValidationPipe(max_size_mb=10)) file: UploadFile
            ):
                ...
        ```
    """

    def __init__(self, max_size_mb: int = 10):
        """Initialize the pipe.

        Args:
            max_size_mb: Maximum file size in megabytes.
        """
        self._max_size = max_size_mb * 1024 * 1024  # Convert to bytes

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Validate file size.

        Args:
            value: The uploaded file.
            metadata: Metadata about the parameter.

        Returns:
            The file if valid.

        Raises:
            ValueError: If file exceeds max size.
        """
        if value is None:
            return None

        # Check if it's a file-like object
        if hasattr(value, "size"):
            if value.size > self._max_size:
                raise ValueError(
                    f"File '{getattr(value, 'filename', 'unknown')}' "
                    f"exceeds maximum size of {self._max_size // (1024 * 1024)}MB",
                )
        elif hasattr(value, "content_length"):
            if value.content_length and value.content_length > self._max_size:
                raise ValueError(
                    f"File exceeds maximum size of {self._max_size // (1024 * 1024)}MB",
                )

        return value


class FileTypeValidationPipe(PipeProtocol):
    """PipeProtocol that validates file MIME types.

    Example:
        ```python
        class UploadController(Controller):
            @post("/upload")
            async def upload(
                self,
                @file(pipe=FileTypeValidationPipe(allowed_types=["image/png", "image/jpeg"])) file: UploadFile
            ):
                ...
        ```
    """

    def __init__(self, allowed_types: list[str] | None = None):
        """Initialize the pipe.

        Args:
            allowed_types: List of allowed MIME types. If None, accepts all.
        """
        self._allowed_types = allowed_types or []

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Validate file type.

        Args:
            value: The uploaded file.
            metadata: Metadata about the parameter.

        Returns:
            The file if valid.

        Raises:
            ValueError: If file type is not allowed.
        """
        if value is None:
            return None

        if not self._allowed_types:
            return value

        # Get content type
        content_type = None
        if hasattr(value, "content_type"):
            content_type = value.content_type
        elif hasattr(value, "headers"):
            content_type = value.headers.get("content-type")

        if content_type and content_type not in self._allowed_types:
            raise ValueError(
                f"File type '{content_type}' not allowed. "
                f"Allowed types: {', '.join(self._allowed_types)}",
            )

        return value


class TrimPipe(PipeProtocol):
    """PipeProtocol that trims whitespace from string inputs.

    Example:
        ```python
        class SearchController(Controller):
            @get("/search")
            async def search(
                self,
                @query(pipe=TrimPipe()) query: str,
            ):
                ...
        ```
    """

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Trim whitespace from string.

        Args:
            value: The value to trim.
            metadata: Metadata about the parameter.

        Returns:
            Trimmed string.
        """
        if value is None:
            return None

        if isinstance(value, str):
            return value.strip()

        return value


__all__ = [
    "FileSizeValidationPipe",
    "FileTypeValidationPipe",
    "TrimPipe",
]
