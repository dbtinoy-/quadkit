"""Tests for file upload pipeline and validators."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile

from quadkit.result import Ok, Result
from quadkit.web.uploads.pipeline import (
    FileExtensionValidator,
    FileSizeValidator,
    FileTypeValidator,
    FileUpload,
    FileUploadPipeline,
    FileValidationError,
)


def _make_upload(
    filename: str = "test.txt",
    content_type: str = "text/plain",
    size: int = 100,
    content: bytes = b"hello",
) -> FileUpload:
    """Create a FileUpload with a mocked UploadFile."""
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=content)
    return FileUpload(
        filename=filename,
        content_type=content_type,
        size=size,
        file=mock_file,
    )


class TestFileUpload:
    """Tests for the FileUpload dataclass."""

    def test_extension(self) -> None:
        upload = _make_upload(filename="photo.jpg")
        assert upload.extension == ".jpg"

    def test_name_without_extension(self) -> None:
        upload = _make_upload(filename="my-file.txt")
        assert upload.name_without_extension == "my-file"

    def test_extension_for_no_extension(self) -> None:
        upload = _make_upload(filename="configfile")
        assert upload.extension == ""

    @pytest.mark.asyncio
    async def test_read_returns_content(self) -> None:
        content = b"file content here"
        upload = _make_upload(content=content)
        result = await upload.read()
        assert result == content

    @pytest.mark.asyncio
    async def test_save_to(self, tmp_path) -> None:
        content = b"save me"
        upload = _make_upload(content=content)
        dest = tmp_path / "output.txt"
        await upload.save_to(dest)
        assert dest.read_bytes() == content

    @pytest.mark.asyncio
    async def test_save_to_creates_parent_dirs(self, tmp_path) -> None:
        content = b"deep save"
        upload = _make_upload(content=content)
        dest = tmp_path / "a" / "b" / "c" / "file.bin"
        await upload.save_to(dest)
        assert dest.read_bytes() == content

    @pytest.mark.asyncio
    async def test_stream_to(self, tmp_path) -> None:
        content = b"x" * 16384  # two 8192-byte chunks
        mock_file = MagicMock(spec=UploadFile)
        # read() called twice: first returns first half, second returns b""
        mock_file.read = AsyncMock(side_effect=[content[:8192], content[8192:], b""])
        upload = FileUpload(
            filename="big.bin",
            content_type="application/octet-stream",
            size=len(content),
            file=mock_file,
        )
        dest = tmp_path / "big.bin"
        await upload.stream_to(dest)
        assert dest.read_bytes() == content


class TestFileSizeValidator:
    @pytest.mark.asyncio
    async def test_passes_when_within_limit(self) -> None:
        validator = FileSizeValidator(max_size_bytes=1000)
        upload = _make_upload(size=500)
        result = await validator.validate(upload)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_returns_err_when_exceeds_limit(self) -> None:
        validator = FileSizeValidator(max_size_bytes=100)
        upload = _make_upload(size=200)
        result = await validator.validate(upload)
        assert result.is_err()
        assert "200" in result.unwrap_err().message


class TestFileTypeValidator:
    @pytest.mark.asyncio
    async def test_passes_for_allowed_type(self) -> None:
        validator = FileTypeValidator(allowed_types=["image/jpeg", "image/png"])
        upload = _make_upload(content_type="image/jpeg")
        result = await validator.validate(upload)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_returns_err_for_disallowed_type(self) -> None:
        validator = FileTypeValidator(allowed_types=["image/jpeg"])
        upload = _make_upload(content_type="application/exe")
        result = await validator.validate(upload)
        assert result.is_err()
        assert "application/exe" in result.unwrap_err().message

    @pytest.mark.asyncio
    async def test_case_insensitive(self) -> None:
        validator = FileTypeValidator(allowed_types=["image/JPEG"])
        upload = _make_upload(content_type="image/jpeg")
        result = await validator.validate(upload)
        assert result.is_ok()


class TestFileExtensionValidator:
    @pytest.mark.asyncio
    async def test_passes_for_allowed_extension(self) -> None:
        validator = FileExtensionValidator(allowed_extensions=[".jpg", ".png"])
        upload = _make_upload(filename="photo.jpg")
        result = await validator.validate(upload)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_returns_err_for_disallowed_extension(self) -> None:
        validator = FileExtensionValidator(allowed_extensions=[".jpg"])
        upload = _make_upload(filename="script.exe")
        result = await validator.validate(upload)
        assert result.is_err()
        assert ".exe" in result.unwrap_err().message


class TestFileUploadPipeline:
    @pytest.mark.asyncio
    async def test_process_with_no_validators(self) -> None:
        pipeline = FileUploadPipeline()
        upload = _make_upload()
        result = await pipeline.process(upload)
        assert result.is_ok()
        assert result.unwrap() is upload

    @pytest.mark.asyncio
    async def test_process_runs_all_validators(self) -> None:
        ordered: list[int] = []

        class _Marker:
            def __init__(self, n: int) -> None:
                self.n = n

            async def validate(self, upload: FileUpload) -> Result[None, FileValidationError]:
                ordered.append(self.n)
                return Ok(None)

        pipeline = FileUploadPipeline(validators=[_Marker(1), _Marker(2)])
        await pipeline.process(_make_upload())
        assert ordered == [1, 2]

    @pytest.mark.asyncio
    async def test_process_returns_err_on_validation_failure(self) -> None:
        pipeline = FileUploadPipeline(
            validators=[FileSizeValidator(max_size_bytes=10)]
        )
        upload = _make_upload(size=999)
        result = await pipeline.process(upload)
        assert result.is_err()
        assert "999" in result.unwrap_err().message

    def test_add_validator_chaining(self) -> None:
        pipeline = FileUploadPipeline()
        result = pipeline.add_validator(FileSizeValidator(100))
        assert result is pipeline  # returns self for chaining

    @pytest.mark.asyncio
    async def test_process_multiple(self) -> None:
        pipeline = FileUploadPipeline()
        uploads = [_make_upload(filename=f"file{i}.txt") for i in range(3)]
        results = await pipeline.process_multiple(uploads)
        assert len(results) == 3
        for r, u in zip(results, uploads, strict=True):
            assert r.is_ok()
            assert r.unwrap() is u
