"""Feature tour: validated file uploads.

Multipart files arrive as Starlette `UploadFile` objects; Quadkit wraps them
in `FileUpload` and runs them through a `FileUploadPipeline` — composable
validators (`FileSizeValidator`, `FileTypeValidator`,
`FileExtensionValidator`) over a typed `Result`. `save_to(base_dir=...)`
refuses path-traversal escapes out of the box.

User code stays boring: wrap, validate, save. Rejection is a typed `Err`,
mapped here to a 422 JSON body.
"""

from pathlib import Path

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, json_response, post
from quadkit.web.config.top_level import SecurityConfig, WebConfig
from quadkit.web.uploads import (
    FileExtensionValidator,
    FileSizeValidator,
    FileTypeValidator,
    FileUpload,
    FileUploadPipeline,
)

UPLOAD_DIR: Path | None = None


class AvatarController(Controller):
    prefix = "/avatars"

    @post("")
    async def upload(self, request: Request) -> dict:
        form = await request.form()
        raw = form.get("file")
        if raw is None:
            return json_response({"error": "file field required"}, status_code=400)

        payload = await raw.read()
        await raw.seek(0)
        upload = FileUpload(
            filename=raw.filename or "unnamed",
            content_type=raw.content_type or "application/octet-stream",
            size=len(payload),
            file=raw,
        )

        pipeline = FileUploadPipeline(
            validators=[
                FileSizeValidator(max_size_bytes=1 * 1024),  # 1 KB for the demo
                FileTypeValidator(allowed_types=["image/png", "image/jpeg"]),
                FileExtensionValidator(allowed_extensions=[".png", ".jpg"]),
            ]
        )

        result = await pipeline.process(upload)
        if result.is_err():
            error = result.unwrap_err()
            return json_response({"error": error.message}, status_code=422)

        destination = UPLOAD_DIR / "avatars" / upload.name_without_extension / upload.filename
        await result.unwrap().save_to(destination)
        return {
            "saved": True,
            "filename": upload.filename,
            "size": upload.size,
            "path": str(destination.relative_to(UPLOAD_DIR)),
        }


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[AvatarController],
            # Machine-to-machine style upload endpoint: CSRF would require a
            # cookie+token round-trip (browser forms); keep the demo focused
            # on the upload pipeline itself.
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
        )
    )
    return app


@pytest.mark.asyncio
async def test_upload_pipeline_accept_and_reject(tmp_path: Path) -> None:
    global UPLOAD_DIR
    UPLOAD_DIR = tmp_path

    async with WebTestBed(create_app()) as bed:
        ok = bed.post(
            "/avatars",
            files={"file": ("pic.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")},
        )
        assert ok.status_code == 200
        assert ok.json["saved"] is True
        assert ok.json["filename"] == "pic.png"
        assert ok.json["size"] == 40
        saved = UPLOAD_DIR / ok.json["path"]
        assert saved.exists()
        assert saved.read_bytes() == b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

        # Wrong extension → 422 with the typed validator's message.
        bad_ext = bed.post(
            "/avatars",
            files={"file": ("run.exe", b"MZ", "application/x-msdownload")},
        )
        assert bad_ext.status_code == 422
        assert "exe" in bad_ext.json["error"].lower() or "." in bad_ext.json["error"]

        # Oversize → 422 on size.
        big = bed.post(
            "/avatars",
            files={"file": ("huge.png", b"\x00" * 2048, "image/png")},
        )
        assert big.status_code == 422

        # Path-traversal prevention — the framework refuses to escape base_dir.
        import io

        from starlette.datastructures import UploadFile as StarletteUploadFile

        evil = FileUpload(
            filename="evil.png",
            content_type="image/png",
            size=2,
            file=StarletteUploadFile(io.BytesIO(b"MZ"), filename="evil.png"),
        )
        with pytest.raises(ValueError, match="escapes base directory"):
            await evil.save_to(tmp_path / "../../../evil.png", base_dir=tmp_path)
