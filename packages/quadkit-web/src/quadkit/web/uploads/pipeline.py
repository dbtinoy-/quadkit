"""File upload handling and validation.

Provides FileUpload model and validation pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import mimetypes
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

import aiofiles
import aiofiles.os

from quadkit.result import Err, Ok, Result
from quadkit.web.exceptions import BadRequestError

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
                    "Upload destination escapes the allowed base directory"
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
                    "Upload destination escapes the allowed base directory"
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
                    message="File exceeds the maximum allowed size",
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
                    message="File type is not allowed",
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
                    message="File extension is not allowed",
                )
            )
        return Ok(None)


def sniff_mime_type(data: bytes) -> str | None:
    """Detect common binary MIME types from magic-byte headers."""
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 5 and data[:5] == b"%PDF-":
        return "application/pdf"
    return None


_SNIFFED_MIMES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
    }
)


class MagicByteValidator(AbstractFileValidator):
    """Verifies binary file headers match declared or allowed MIME types."""

    def __init__(self, allowed_types: list[str] | tuple[str, ...] | None = None):
        self._allowed = (
            frozenset(t.lower() for t in allowed_types)
            if allowed_types is not None
            else None
        )

    async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
        """Read header bytes (rewinding when supported) and verify magic signature."""
        header = await upload.file.read(16)
        seek = getattr(upload.file, "seek", None)
        if callable(seek):
            maybe_coro = seek(0)
            if hasattr(maybe_coro, "__await__"):
                await maybe_coro
        return validate_magic_bytes(
            header,
            declared_content_type=upload.content_type,
            allowed_types=self._allowed,
        )


def validate_magic_bytes(
    data: bytes,
    *,
    declared_content_type: str | None = None,
    allowed_types: frozenset[str]
    | set[str]
    | list[str]
    | tuple[str, ...]
    | None = None,
) -> Result[None, FileValidationError]:
    """Validate *data* magic-byte signature against declared and allowed MIME types."""
    sniffed = sniff_mime_type(data)
    declared = (declared_content_type or "").lower()
    allowed_set = (
        frozenset(t.lower() for t in allowed_types)
        if allowed_types is not None
        else None
    )

    if declared in _SNIFFED_MIMES and sniffed != declared:
        return Err(
            FileValidationError(
                message=(
                    f"File header signature ({sniffed or 'unknown'}) does not match "
                    f"declared content type '{declared_content_type}'"
                )
            )
        )

    if allowed_set is not None and sniffed is not None and sniffed not in allowed_set:
        return Err(
            FileValidationError(
                message=f"Detected file type '{sniffed}' is not allowed"
            )
        )

    return Ok(None)


def validate_upload_metadata(
    content_type: str,
    size_bytes: int,
    *,
    max_size_bytes: int,
    allowed_types: list[str] | tuple[str, ...],
) -> Result[None, FileValidationError]:
    """Validate upload MIME type and byte size before streaming or presigning."""
    normalized_allowed = [t.lower() for t in allowed_types]
    if content_type.lower() not in normalized_allowed:
        return Err(
            FileValidationError(
                message=f"Content type '{content_type}' not allowed",
            )
        )
    if size_bytes > max_size_bytes:
        return Err(
            FileValidationError(
                message=f"File size {size_bytes} exceeds maximum {max_size_bytes} bytes",
            )
        )
    return Ok(None)


def validate_upload_bytes(
    data: bytes,
    content_type: str,
    *,
    max_size_bytes: int,
    allowed_types: list[str] | tuple[str, ...],
    verify_magic_bytes: bool = True,
) -> Result[None, FileValidationError]:
    """Validate in-memory upload bytes for MIME type, size limit, and magic signature."""
    meta_res = validate_upload_metadata(
        content_type,
        len(data),
        max_size_bytes=max_size_bytes,
        allowed_types=allowed_types,
    )
    if meta_res.is_err():
        return meta_res
    if verify_magic_bytes:
        return validate_magic_bytes(
            data,
            declared_content_type=content_type,
            allowed_types=allowed_types,
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


SAFE_MEDIA_RESPONSE_HEADERS: dict[str, str] = {
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Cache-Control": "public, max-age=86400",
    "X-Content-Type-Options": "nosniff",
}

_CANONICAL_MIME_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


def extension_for_mime_type(content_type: str | None) -> str:
    """Return a storage-safe file extension derived from a validated MIME type."""
    if not content_type:
        return ""
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in _CANONICAL_MIME_EXTENSIONS:
        return _CANONICAL_MIME_EXTENSIONS[normalized]
    ext = mimetypes.guess_extension(normalized)
    if ext == ".jpe":
        return ".jpg"
    return ext or ""


def sanitize_blob_key(raw_path: str) -> str:
    """Validate and normalize a relative blob storage key, rejecting traversal attempts."""
    if (
        not raw_path
        or "\x00" in raw_path
        or "\\" in raw_path
        or raw_path.startswith("/")
    ):
        raise BadRequestError("Invalid storage path")
    parts = PurePosixPath(raw_path).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise BadRequestError("Invalid storage path")
    return "/".join(parts)
