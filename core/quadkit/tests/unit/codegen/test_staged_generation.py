"""Tests for atomic staged generation on GeneratorBase."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.codegen.base import GeneratorBase
from quadkit.contracts.cli.generators import (
    CollisionPolicy,
    GenerationOptions,
    GenerationResult,
)
from quadkit.contracts.exceptions.infra import CollidingFileError


class BareGenerator(GeneratorBase):
    def generate(self, name: str, **options: object) -> GenerationResult:
        return self.commit(GenerationOptions())


@pytest.fixture
def gen(tmp_path: Path) -> BareGenerator:
    return BareGenerator(output_dir=tmp_path / "out")


class TestStageAndCommit:
    def test_commit_writes_sorted_tree_byte_exact(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        gen.stage("models/b.py", "B")
        gen.stage("models/a.py", "A")
        gen.stage("controllers/c.py", "C")

        result = gen.commit(GenerationOptions())

        assert [str(p) for p in result.files_created] == sorted(
            str(p) for p in result.files_created
        )
        assert len(result.files_created) == 3
        assert (tmp_path / "out/models/a.py").read_text() == "A"
        assert (tmp_path / "out/controllers/c.py").read_text() == "C"

    def test_duplicate_stage_raises_immediately(self, gen: BareGenerator) -> None:
        gen.stage("x.py", "one")
        with pytest.raises(ValueError, match="already staged"):
            gen.stage("x.py", "two")

    def test_traversal_guard_fires_at_stage_time(self, gen: BareGenerator) -> None:
        with pytest.raises(ValueError, match="escapes output directory"):
            gen.stage("../escape.py", "nope")

    def test_stage_accepts_absolute_paths_inside_output(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        target = tmp_path / "out" / "abs.py"
        gen.stage(target, "ok")
        result = gen.commit(GenerationOptions())
        assert target in result.files_created


class TestCollisionPoliciesOnCommit:
    def test_skip_leaves_existing_file_untouched(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        existing = tmp_path / "out/x.py"
        existing.parent.mkdir(parents=True)
        existing.write_text("original")
        gen.stage("x.py", "new")

        result = gen.commit(GenerationOptions())

        assert existing.read_text() == "original"
        assert existing in result.files_skipped

    def test_overwrite_replaces_and_reports(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        existing = tmp_path / "out/x.py"
        existing.parent.mkdir(parents=True)
        existing.write_text("original")
        gen.stage("x.py", "new")

        result = gen.commit(GenerationOptions(policy=CollisionPolicy.OVERWRITE))

        assert existing.read_text() == "new"
        assert existing in result.files_overwritten

    def test_force_alias_resolves_to_overwrite(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        existing = tmp_path / "out/x.py"
        existing.parent.mkdir(parents=True)
        existing.write_text("original")
        gen.stage("x.py", "new")

        result = gen.commit(GenerationOptions(force=True))

        assert existing.read_text() == "new"
        assert existing in result.files_overwritten

    def test_fail_policy_raises_without_partial_writes(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        colliding = tmp_path / "out/b.py"
        colliding.parent.mkdir(parents=True)
        colliding.write_text("keep")
        gen.stage("a.py", "A")
        gen.stage("b.py", "B")

        with pytest.raises(CollidingFileError):
            gen.commit(GenerationOptions(policy=CollisionPolicy.FAIL))

        assert colliding.read_text() == "keep"
        assert not (tmp_path / "out/a.py").exists()


class TestDryRun:
    def test_dry_run_touches_nothing_but_reports_actions(
        self, gen: BareGenerator, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        existing = out_dir / "x.py"
        existing.parent.mkdir(parents=True)
        existing.write_text("orig")
        gen.stage("x.py", "new")
        gen.stage("y.py", "Y")

        result = gen.commit(GenerationOptions(dry_run=True))

        assert existing.read_text() == "orig"
        assert not (out_dir / "y.py").exists()
        assert existing in result.files_skipped
        assert (out_dir / "y.py") in result.files_created


class TestFinalizeAndLifecycle:
    def test_finalize_default_is_identity(self, tmp_path: Path) -> None:
        gen = BareGenerator(output_dir=tmp_path / "o")
        gen.stage("f.py", "F")
        result = gen.commit(GenerationOptions())
        assert gen.finalize(result) is result

    def test_commit_clears_staged_set(self, gen: BareGenerator) -> None:
        gen.stage("once.py", "1")
        gen.commit(GenerationOptions())
        empty = gen.commit(GenerationOptions())
        assert empty.to_manifest() == {}
