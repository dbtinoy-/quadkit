"""Request and multipart upload transport primitives for quadkit-web."""

from __future__ import annotations

from starlette.datastructures import UploadFile
from starlette.requests import Request

__all__ = ["Request", "UploadFile"]
