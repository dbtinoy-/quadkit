"""Feature tour: response shaping.

Four one-liners cover the response spectrum:

* `file_response(path, filename=...)` — downloads with correct disposition
* `streaming_response(generator)` — chunked big payloads without buffering
* `html_response("<h1>…")` — server-rendered fragments (HTMX-ready)
* `redirect_response("/there")` — plain redirects

…plus the zero-line one: returning a bare `str` renders `text/html`.
"""

from collections.abc import AsyncGenerator
import csv
from pathlib import Path

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import (
    Controller,
    WebModule,
    file_response,
    get,
    html_response,
    redirect_response,
    streaming_response,
)


def _csv_path(tmp_dir: Path) -> Path:
    path = tmp_dir / "report.csv"
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "user"])
        writer.writerow(["1", "ada"])
        writer.writerow(["2", "grace"])
    return path


class ExportController(Controller):
    prefix = "/export"
    csv_file: Path | None = None

    @get("/report.csv")
    async def download(self) -> object:
        return file_response(
            self.csv_file,
            media_type="text/csv",
            filename="report.csv",
        )

    @get("/row-stream")
    async def chunked(self) -> object:
        async def rows() -> AsyncGenerator[bytes, None]:
            yield b"id,user\n"
            yield b"1,ada\n"
            yield b"2,grace\n"

        return streaming_response(rows(), media_type="text/csv")

    @get("/fragment")
    async def fragment(self) -> object:
        return html_response("<h1>2 rows exported</h1>")

    @get("/welcome")
    async def welcome(self) -> str:
        # Bare string → text/html, HTMX-friendly by default.
        return "<p>welcome back</p>"

    @get("/old-report")
    async def legacy(self) -> object:
        return redirect_response("/export/report.csv", status_code=302)


@pytest.mark.asyncio
async def test_response_shaping(tmp_path: Path) -> None:
    ExportController.csv_file = _csv_path(tmp_path)

    app = Application()
    app.add_module(WebModule.configure(controllers=[ExportController]))

    async with WebTestBed(app) as bed:
        download = bed.get("/export/report.csv", follow_redirects=True)
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("text/csv")
        assert "attachment" in download.headers["content-disposition"]
        assert download.text == "id,user\r\n1,ada\r\n2,grace\r\n"

        streamed = bed.get("/export/row-stream")
        assert streamed.status_code == 200
        assert streamed.text == "id,user\n1,ada\n2,grace\n"

        fragment = bed.get("/export/fragment")
        assert fragment.headers["content-type"] == "text/html; charset=utf-8"
        assert fragment.text == "<h1>2 rows exported</h1>"

        welcome = bed.get("/export/welcome")
        assert welcome.headers["content-type"] == "text/html; charset=utf-8"
        assert welcome.text == "<p>welcome back</p>"

        legacy = bed.get("/export/old-report", follow_redirects=False)
        assert legacy.status_code == 302
        assert legacy.headers["location"] == "/export/report.csv"
