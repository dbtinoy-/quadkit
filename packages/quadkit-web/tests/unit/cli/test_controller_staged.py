"""Staged-generation behavior tests for ControllerGenerator adoption."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.contracts.cli.generators import CollisionPolicy, GenerationOptions
from quadkit.testing.generators import assert_generated_tree
from quadkit.web.cli.generators import ControllerGenerator


def _gen(tmp_path: Path) -> ControllerGenerator:
    return ControllerGenerator(output_dir=tmp_path / "out")


def test_default_skip_leaves_existing_file(tmp_path: Path) -> None:
    out_file = tmp_path / "out" / "message_controller.py"
    out_file.parent.mkdir(parents=True)
    out_file.write_text("original")
    gen = _gen(tmp_path)

    result = gen.generate("Message")

    assert out_file.read_text() == "original"
    assert out_file in result.files_skipped
    assert result.files_created == []


def test_generate_is_deterministic_across_runs(tmp_path: Path) -> None:
    first_root = tmp_path / "one"
    second_root = tmp_path / "two"
    gen_one = ControllerGenerator(output_dir=first_root)
    gen_two = ControllerGenerator(output_dir=second_root)

    gen_one.generate("Message", path="/api/messages")
    result = assert_generated_tree(
        gen_two,
        "Message",
        root=second_root,
        expected_files={
            "message_controller.py": (
                (first_root / "message_controller.py").read_text()
            )
        },
        path="/api/messages",
    )
    assert len(result.files_created) == 1


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    gen = _gen(tmp_path)
    result = gen.generate("Message", dry_run=True)

    assert not (tmp_path / "out" / "message_controller.py").exists()
    assert (tmp_path / "out" / "message_controller.py") in result.files_created


def test_force_overwrites_existing(tmp_path: Path) -> None:
    out_file = tmp_path / "out" / "message_controller.py"
    out_file.parent.mkdir(parents=True)
    out_file.write_text("stale")
    gen = _gen(tmp_path)

    result = gen.generate("Message", force=True)

    assert "Controller" in out_file.read_text()
    assert out_file in result.files_overwritten


def test_duplicate_stage_rejected_before_commit(tmp_path: Path) -> None:
    gen = _gen(tmp_path)
    gen.stage(Path(tmp_path / "out" / "x.py"), "1")
    with pytest.raises(ValueError, match="already staged"):
        gen.stage(Path(tmp_path / "out" / "x.py"), "2")
    # Nothing was written by the rejected staging session.
    assert not (tmp_path / "out" / "x.py").exists()


def test_fail_policy_at_staging_level(tmp_path: Path) -> None:
    from quadkit.contracts.exceptions.infra import CollidingFileError

    existing = tmp_path / "out" / "y.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("keep")
    gen = _gen(tmp_path)
    gen.stage(existing, "new")

    with pytest.raises(CollidingFileError):
        gen.commit(GenerationOptions(policy=CollisionPolicy.FAIL))

    assert existing.read_text() == "keep"
