"""S3 upload mixin for S3Driver: single-part and multipart upload logic."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime
import hashlib
from typing import Any, cast

# Optional imports
try:
    import botocore.exceptions
except ImportError:
    botocore = None

from quadkit.contracts.infra.storage import FileInfo, Uploadable, UploadOptions
from quadkit.logging import get_logger
from quadkit.storage.exceptions import StorageError
from quadkit.storage.lib.content_type import get_content_type

logger = get_logger(__name__)


class _S3UploadMixin:
    """Upload mixin: single-part and multipart upload for S3Driver."""

    # Attributes provided by S3Driver at runtime
    bucket: str
    multipart_chunk_size: int
    multipart_threshold: int
    _get_client: Any
    _build_sse_params: Any
    _normalize_path: Any
    _get_file_size: Any
    _normalize_upload_options: Any

    async def _upload_small_file(
        self,
        key: str,
        data: Uploadable,
        options: UploadOptions | None = None,
    ) -> FileInfo:
        """Upload small file using single put_object"""
        # Prepare upload parameters
        put_params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
        }

        # Handle different data types
        if isinstance(data, bytes):
            put_params["Body"] = data
        elif isinstance(data, str):
            put_params["Body"] = data.encode("utf-8")
        elif hasattr(data, "read"):  # BinaryIO
            content = data.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            put_params["Body"] = content
        elif hasattr(data, "__aiter__"):  # AsyncIterator
            # Collect all chunks into memory for small files
            chunks = []
            async for chunk in data:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                chunks.append(chunk)
            put_params["Body"] = b"".join(chunks)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        # Add content type
        content_type = (
            options.content_type
            if options and options.content_type
            else get_content_type(key)
        )
        put_params["ContentType"] = content_type

        # Add metadata
        if options and options.metadata:
            put_params["Metadata"] = options.metadata

        # Add ACL if public
        if options and options.public:
            put_params["ACL"] = "public-read"

        # Add server-side encryption parameters
        put_params.update(self._build_sse_params())

        # Upload
        try:
            response = await (await self._get_client()).put_object(**put_params)
            logger.info("upload: single-part upload complete key=%s", key)

            # Get file info from response
            return FileInfo(
                path=key,
                size=len(put_params["Body"]),
                content_type=content_type,
                last_modified=datetime.now(UTC),  # S3 doesn't return this immediately
                etag=response.get("ETag", ""),
                metadata=options.metadata if options else None,
            )
        except botocore.exceptions.ClientError as e:
            logger.exception(
                "upload: S3 put_object failed key=%s",
                key,
            )
            raise StorageError(
                f"S3 upload failed for {key!r}: {e}",
                details={"bucket": self.bucket, "key": key},
                hint="Check S3 credentials, bucket write permissions, and network connectivity.",
            ) from e

    async def _upload_large_file(
        self,
        key: str,
        data: Uploadable,
        options: UploadOptions | None = None,
    ) -> FileInfo:
        """Upload large file using multipart upload"""
        # Start multipart upload
        create_params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
        }

        # Add content type
        content_type = (
            options.content_type
            if options and options.content_type
            else get_content_type(key)
        )
        create_params["ContentType"] = content_type

        # Add metadata
        if options and options.metadata:
            create_params["Metadata"] = options.metadata

        # Add ACL if public
        if options and options.public:
            create_params["ACL"] = "public-read"

        # Add server-side encryption parameters
        create_params.update(self._build_sse_params())

        try:
            upload_response = (await self._get_client()).create_multipart_upload(
                **create_params,
            )
            upload_id = upload_response["UploadId"]
            logger.info(
                "upload: multipart upload started key=%s upload_id=%s",
                key,
                upload_id,
            )

            parts = []
            part_number = 1
            total_size = 0

            # Handle different data types for chunking
            if isinstance(data, (bytes, str)):
                # For bytes/str, chunk in memory
                content = data.encode("utf-8") if isinstance(data, str) else data

                total_size = len(content)

                for i in range(0, len(content), self.multipart_chunk_size):
                    chunk = content[i : i + self.multipart_chunk_size]

                    # Compute per-chunk checksum for integrity verification (M36)
                    chunk_sha256 = base64.b64encode(
                        hashlib.sha256(chunk).digest()
                    ).decode()

                    # Upload part
                    part_response = (await self._get_client()).upload_part(
                        Bucket=self.bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk,
                        ChecksumSHA256=chunk_sha256,
                    )

                    parts.append(
                        {
                            "PartNumber": part_number,
                            "ETag": part_response["ETag"],
                            "ChecksumSHA256": chunk_sha256,
                        },
                    )
                    part_number += 1

            elif hasattr(data, "read"):  # BinaryIO
                # For file-like objects, read in chunks
                while True:
                    chunk = data.read(self.multipart_chunk_size)
                    if not chunk:
                        break

                    # Normalise chunk to bytes for typing and downstream calls
                    if isinstance(chunk, (bytes, bytearray)):
                        chunk_bytes = bytes(chunk)
                    else:
                        # GuardProtocol against unexpected shapes (e.g., tests returning str)
                        chunk_bytes = str(chunk).encode("utf-8")

                    total_size += len(chunk_bytes)

                    # Compute per-chunk checksum for integrity verification (M36)
                    chunk_sha256 = base64.b64encode(
                        hashlib.sha256(chunk_bytes).digest()
                    ).decode()

                    # Upload part
                    part_response = (await self._get_client()).upload_part(
                        Bucket=self.bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk_bytes,
                        ChecksumSHA256=chunk_sha256,
                    )

                    parts.append(
                        {
                            "PartNumber": part_number,
                            "ETag": part_response["ETag"],
                            "ChecksumSHA256": chunk_sha256,
                        },
                    )
                    part_number += 1

            elif hasattr(data, "__aiter__"):  # AsyncIterator
                # For async iterators, process chunks as they come
                async for raw_chunk in data:
                    # Normalise chunk to bytes for typing and downstream calls
                    if isinstance(raw_chunk, str):
                        chunk_bytes = raw_chunk.encode("utf-8")
                    elif isinstance(raw_chunk, (bytes, bytearray)):
                        chunk_bytes = bytes(raw_chunk)
                    else:
                        chunk_bytes = cast("bytes", raw_chunk)

                    total_size += len(chunk_bytes)

                    # Compute per-chunk checksum for integrity verification (M36)
                    chunk_sha256 = base64.b64encode(
                        hashlib.sha256(chunk_bytes).digest()
                    ).decode()

                    # Upload part
                    part_response = (await self._get_client()).upload_part(
                        Bucket=self.bucket,
                        Key=key,
                        UploadId=upload_id,
                        PartNumber=part_number,
                        Body=chunk_bytes,
                        ChecksumSHA256=chunk_sha256,
                    )

                    parts.append(
                        {
                            "PartNumber": part_number,
                            "ETag": part_response["ETag"],
                            "ChecksumSHA256": chunk_sha256,
                        },
                    )
                    part_number += 1
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")

            # Complete multipart upload
            complete_response = (await self._get_client()).complete_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            logger.info(
                "upload: multipart upload complete key=%s parts=%d size=%d",
                key,
                len(parts),
                total_size,
            )

            return FileInfo(
                path=key,
                size=total_size,
                content_type=content_type,
                last_modified=datetime.now(UTC),
                etag=complete_response.get("ETag", ""),
                metadata=options.metadata if options else None,
            )

        except asyncio.CancelledError:
            # Propagate cancellation to allow task to be cancelled by caller
            raise
        except Exception as e:
            # Abort multipart upload on any error
            try:
                if "upload_id" in locals():
                    (await self._get_client()).abort_multipart_upload(
                        Bucket=self.bucket,
                        Key=key,
                        UploadId=upload_id,
                    )
                    logger.info(
                        "upload: aborted multipart upload key=%s upload_id=%s",
                        key,
                        upload_id,
                    )
            except BaseException:
                # Include full traceback to aid diagnosing abort failures
                logger.exception(
                    "upload: failed to abort multipart upload key=%s upload_id=%s",
                    key,
                    upload_id,
                )

            # Log multipart upload failure with traceback so root cause is preserved
            logger.exception("upload: multipart upload failed key=%s", key)
            if isinstance(e, botocore.exceptions.ClientError):
                raise StorageError(
                    f"S3 multipart upload failed for {key!r}: {e}",
                    details={"bucket": self.bucket, "key": key},
                    hint="Check S3 credentials and bucket write permissions. Consider increasing multipart_threshold.",
                ) from e
            raise StorageError(
                f"Multipart upload failed for {key!r}: {e}",
                details={"bucket": self.bucket, "key": key},
                hint="An error occurred during multipart upload. Check network connectivity and retry.",
            ) from e

    async def upload(
        self,
        path: str,
        data: Uploadable,
        content_type: UploadOptions | str | None = None,
        **options: Any,
    ) -> FileInfo:
        """Upload data to S3 with automatic multipart upload for large files"""
        key = self._normalize_path(path)

        # Build upload options from the protocol-compatible signature.
        opt = self._normalize_upload_options(content_type, options)

        # Determine file size to choose upload strategy
        file_size = await self._get_file_size(data)

        if file_size < self.multipart_threshold:
            # Small file - single upload
            return await self._upload_small_file(key, data, opt)
        # Large file - multipart upload
        return await self._upload_large_file(key, data, opt)
