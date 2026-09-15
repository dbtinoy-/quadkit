from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from quadkit.cli.lib.templates import TemplateRenderer


class TestTemplateRenderer:
    def test_init(self) -> None:
        renderer = TemplateRenderer("/tmp/templates")
        assert str(renderer.templates_dir) == "/tmp/templates"
        assert renderer.env is not None

    def test_init_with_path(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        renderer = TemplateRenderer(templates_dir)
        assert renderer.templates_dir == templates_dir

    def test_renders_template(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.txt.j2").write_text("Hello {{ name }}!")
        renderer = TemplateRenderer(templates_dir)
        result = renderer.render("hello.txt.j2", {"name": "World"})
        assert result == "Hello World!"

    def test_render_to_file(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.txt.j2").write_text("Hello {{ name }}!")
        renderer = TemplateRenderer(templates_dir)

        output_path = tmp_path / "output" / "hello.txt"
        result = renderer.render_to_file("hello.txt.j2", output_path, {"name": "World"})
        assert result == output_path
        assert output_path.read_text() == "Hello World!"

    def test_render_to_file_existing_no_overwrite(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.txt.j2").write_text("Hello {{ name }}!")
        renderer = TemplateRenderer(templates_dir)

        output_path = tmp_path / "output.txt"
        output_path.write_text("existing")

        with pytest.raises(FileExistsError):
            renderer.render_to_file("hello.txt.j2", output_path, {"name": "World"})

    def test_render_to_file_overwrite(self, tmp_path: Path) -> None:
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        (templates_dir / "hello.txt.j2").write_text("Hello {{ name }}!")
        renderer = TemplateRenderer(templates_dir)

        output_path = tmp_path / "output.txt"
        output_path.write_text("existing")

        result = renderer.render_to_file("hello.txt.j2", output_path, {"name": "World"}, overwrite=True)
        assert result == output_path
        assert output_path.read_text() == "Hello World!"

    def test_render_template_not_found(self) -> None:
        renderer = TemplateRenderer("/tmp/nonexistent_templates")
        with pytest.raises(Exception):
            renderer.render("nonexistent.j2", {})
