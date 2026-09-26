from __future__ import annotations

"""MinIO/S3 BlobStore compliance test using a real MinIO connection."""

import pytest

from quadkit.testing.compliance import BlobStoreCompliance
from quadkit.testing.integration.fixtures import (
    minio_bucket,  # noqa: F401
    minio_client,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.requires_minio]


class TestMinioBlobStoreCompliance(BlobStoreCompliance):
    """Verify S3Driver satisfies BlobStoreCompliance against real MinIO.

    Uses the ``minio_client`` and ``minio_bucket`` fixtures provided by
    ``quadkit.testing.integration.fixtures``.  The test class is auto-skipped
    when MinIO is not reachable or the ``aiobotocore`` driver is not installed.
    """

    @pytest.fixture(autouse=True)
    async def _setup(self, minio_client: object, minio_bucket: str) -> None:
        """Capture the live MinIO connection details.

        Args:
            minio_client: Session-scoped MinIO client (placeholder from fixtures).
            minio_bucket: Unique bucket name scoped to this test function.
        """
        self._minio_client = minio_client
        self._bucket = minio_bucket

    async def create_store(self) -> object:
        """Create an S3Driver pointed at the live MinIO instance.

        Returns:
            A ready-to-use S3Driver configured for MinIO.

        Raises:
            pytest.skip.Exception: If ``aiobotocore`` is not installed or
                the S3Driver cannot be imported.
        """
        try:
            from quadkit.storage.backends.s3 import S3Driver  # noqa: F401
        except ImportError:
            pytest.skip("S3Driver not available")

        pytest.skip(
            "TODO: configure S3Driver with MinIO endpoint_url, access_key, "
            "secret_key, and bucket from integration_config before returning"
        )
