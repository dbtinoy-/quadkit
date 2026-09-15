"""Tests for `quadkit run` entry-point auto-detection."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from quadkit.cli.lib.entry_point import detect_factory_attr as _detect_factory_attr


class TestDetectFactoryAttr:
    def test_detects_create_app_function(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("def create_app(): ...")
        assert _detect_factory_attr(str(f)) == "create_app"

    def test_detects_app_assignment(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("app = SomeASGI()")
        assert _detect_factory_attr(str(f)) == "app"

    def test_detects_app_from_import(self, tmp_path: Path) -> None:
        """Gear-1 style: `from quadkit.web import app, get`."""
        f = tmp_path / "app.py"
        f.write_text(textwrap.dedent("""\
            from quadkit.web import app, get

            @get("/")
            async def hello() -> dict:
                return {"hello": "world"}
        """))
        assert _detect_factory_attr(str(f)) == "app"

    def test_prefers_create_app_over_app(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("from quadkit.web import app\ndef create_app(): ...")
        assert _detect_factory_attr(str(f)) == "create_app"

    def test_returns_none_when_no_match(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1")
        assert _detect_factory_attr(str(f)) is None

    def test_returns_none_on_syntax_error(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("def (broken")
        assert _detect_factory_attr(str(f)) is None
