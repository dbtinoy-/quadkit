"""Tests for the generator base class."""

import pytest
from pathlib import Path

from quadkit.cli.generators.base import GeneratorBase, GenerationResult


class TestBaseGenerator:
    def test_generator_has_required_attributes(self):
        class TestGenerator(GeneratorBase):
            template_name = "test.jinja2"

            def get_context(self, name: str, **kwargs):
                return {"name": name}

        gen = TestGenerator(output_dir=Path.cwd())
        assert gen.output_dir is not None

    def test_generation_result_tracks_files(self):
        result = GenerationResult()
        path = Path("test.py")
        result.files_created.append(path)
        assert len(result.files_created) == 1
        assert result.files_created[0] == path

    def test_dry_run_does_not_write(self, tmp_path):
        from quadkit.cli.generators.provider import ProviderGenerator
        gen = ProviderGenerator(output_dir=str(tmp_path))
        result = gen.generate("TestProvider", dry_run=True)
        assert not (tmp_path / "test_provider_provider.py").exists()

    def test_file_conflict_detection(self, tmp_path):
        from quadkit.cli.generators.provider import ProviderGenerator
        gen = ProviderGenerator(output_dir=str(tmp_path))
        gen.generate("test", dry_run=False, force=False)
        result = gen.generate("test", dry_run=False, force=False)
        assert len(result.files_skipped) > 0

    def test_force_overwrites_existing(self, tmp_path):
        from quadkit.cli.generators.provider import ProviderGenerator
        gen = ProviderGenerator(output_dir=str(tmp_path))
        result = gen.generate("test", dry_run=False, force=True)
        assert len(result.files_created) > 0 or len(result.files_overwritten) > 0
