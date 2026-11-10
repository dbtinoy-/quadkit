"""Unit tests for Request and UploadFile re-exports from quadkit.web."""

from __future__ import annotations

from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.requests import Request as StarletteRequest

from quadkit.web import Request, UploadFile
from quadkit.web.transport import Request as TransportRequest
from quadkit.web.transport import UploadFile as TransportUploadFile


def test_request_and_upload_file_exported_from_quadkit_web() -> None:
    assert Request is StarletteRequest
    assert UploadFile is StarletteUploadFile
    assert TransportRequest is StarletteRequest
    assert TransportUploadFile is StarletteUploadFile
