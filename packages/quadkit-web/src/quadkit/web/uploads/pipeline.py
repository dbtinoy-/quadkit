"""File upload handling and validation.

Provides FileUpload model and validation pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.os

from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from starlette.datastructures import UploadFile


@dataclass(frozen=True)
class FileUpload:
    """Represents an uploaded file with metadata."""

    filename: str
    content_type: str
    size: int
    file: UploadFile

    @property
    def extension(self) -> str:
        """Get file extension."""
        return Path(self.filename).suffix.lower()

    @property
    def name_without_extension(self) -> str:
        """Get filename without extension."""
        return Path(self.filename).stem

    async def read(self) -> bytes:
        """Read the entire file content."""
        return await self.file.read()

    async def save_to(
        self, path: str | Path, base_dir: Path | str | None = None
    ) -> None:
        """Save the file to a path.

        Args:
            path: Destination path for the file.
            base_dir: Optional base directory.  When provided, the resolved
                destination path must be relative to ``base_dir``; if it would
                escape that directory (e.g. via ``../../``), a
                :exc:`ValueError` is raised.

        Raises:
            ValueError: If ``base_dir`` is provided and the resolved path
                escapes it (path-traversal prevention).
        """
        path = Path(path)
        if base_dir is not None:
            resolved = path.resolve()
            base = Path(base_dir).resolve()
            if not resolved.is_relative_to(base):
                raise ValueError(
                    f"Path {str(path)!r} escapes base directory {str(base_dir)!r}"
                )
        await aiofiles.os.makedirs(path.parent, exist_ok=True)

        content = await self.read()
        async with aiofiles.open(path, "wb") as f:
            await f.write(content)

    async def stream_to(
        self,
        path: str | Path,
        chunk_size: int = 8192,
        base_dir: Path | str | None = None,
    ) -> None:
        """Stream file to disk in chunks.

        Args:
            path: Destination path for the file.
            chunk_size: Number of bytes per read/write iteration.
            base_dir: Optional base directory.  When provided, the resolved
                destination path must be relative to ``base_dir``; if it would
                escape that directory (e.g. via ``../../``), a
                :exc:`ValueError` is raised.

        Raises:
            ValueError: If ``base_dir`` is provided and the resolved path
                escapes it (path-traversal prevention).
        """
        path = Path(path)
        if base_dir is not None:
            resolved = path.resolve()
            base = Path(base_dir).resolve()
            if not resolved.is_relative_to(base):
                raise ValueError(
                    f"Path {str(path)!r} escapes base directory {str(base_dir)!r}"
                )
        await aiofiles.os.makedirs(path.parent, exist_ok=True)

        async with aiofiles.open(path, "wb") as f:
            while True:
                chunk = await self.file.read(chunk_size)
                if not chunk:
                    break
                await f.write(chunk)


class AbstractFileValidator(ABC):
    """Base class for file validation."""

    @abstractmethod
    async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
        """Validate the file.

        Args:
            upload: The file upload to validate.

        Returns:
            Ok(None) if validation passes, Err(FileValidationError) if it fails.
        """


@dataclass(frozen=True)
class FileValidationError:
    """Error type for file validation failures."""

    message: str


class FileSizeValidator(AbstractFileValidator):
    """Validates file size."""

    def __init__(self, max_size_bytes: int):
        self.max_size = max_size_bytes

    async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
        """Validate file size against the configured maximum.

        Args:
            upload: The file upload to validate.

        Returns:
            Ok(None) if size is within the limit, Err(FileValidationError) if exceeded.
        """
        if upload.size > self.max_size:
            return Err(
                FileValidationError(
                    message=f"File size {upload.size} exceeds maximum {self.max_size}",
                )
            )
        return Ok(None)


class FileTypeValidator(AbstractFileValidator):
    """Validates file MIME type."""

    def __init__(self, allowed_types: list[str]):
        self.allowed_types = [t.lower() for t in allowed_types]

    async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
        """Validate file MIME type against allowed types.

        Args:
            upload: The file upload to validate.

        Returns:
            Ok(None) if type is allowed, Err(FileValidationError) if disallowed.
        """
        if upload.content_type.lower() not in self.allowed_types:
            return Err(
                FileValidationError(
                    message=f"File type {upload.content_type} not allowed. "
                    f"Allowed: {self.allowed_types}",
                )
            )
        return Ok(None)


class FileExtensionValidator(AbstractFileValidator):
    """Validates file extension."""

    def __init__(self, allowed_extensions: list[str]):
        self.allowed_extensions = [e.lower() for e in allowed_extensions]

    async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
        """Validate file extension against allowed extensions.

        Args:
            upload: The file upload to validate.

        Returns:
            Ok(None) if extension is allowed, Err(FileValidationError) if disallowed.
        """
        if upload.extension not in self.allowed_extensions:
            return Err(
                FileValidationError(
                    message=f"File extension {upload.extension} not allowed. "
                    f"Allowed: {self.allowed_extensions}",
                )
            )
        return Ok(None)


class FileUploadPipeline:
    """Pipeline for processing file uploads with validation."""

    def __init__(self, validators: list[AbstractFileValidator] | None = None):
        self.validators = validators or []

    def add_validator(self, validator: AbstractFileValidator) -> FileUploadPipeline:
        """Add a validator to the pipeline."""
        self.validators.append(validator)
        return self

    async def process(
        self, upload: FileUpload
    ) -> Result[FileUpload, FileValidationError]:
        """Process and validate a file upload.

        Args:
            upload: The file upload to process.

        Returns:
            Ok(upload) if all validators pass, Err(FileValidationError) on first failure.
        """
        for validator in self.validators:
            result = await validator.validate(upload)
            if result.is_err():
                return Err(result.unwrap_err())
        return Ok(upload)

    async def process_multiple(
        self,
        uploads: list[FileUpload],
    ) -> list[Result[FileUpload, FileValidationError]]:
        """Process multiple file uploads."""
        results = []
        for upload in uploads:
            results.append(await self.process(upload))
        return results
