"""Staged-generation behavior tests for DatabaseRepositoryGenerator adoption."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.testing.generators import assert_generated_tree
from quadkit.sql.cli.generators.database_repository import (
    DatabaseRepositoryGenerator,
)


def _gen(tmp_path: Path) -> DatabaseRepositoryGenerator:
    return DatabaseRepositoryGenerator(output_dir=tmp_path / "out")


def test_generate_is_deterministic_across_runs(tmp_path: Path) -> None:
    first_root = tmp_path / "one"
    second_root = tmp_path / "two"
    gen_one = _gen_with(first_root)
    gen_two = _gen_with(second_root)

    gen_one.generate("Order", fields_str="total:float,placed_at:datetime?")
    content = (first_root / "order_repository.py").read_text()

    result = assert_generated_tree(
        gen_two,
        "Order",
        root=second_root,
        expected_files={"order_repository.py": content},
        fields_str="total:float,placed_at:datetime?",
    )
    assert len(result.files_created) == 1


def _gen_with(root: Path) -> DatabaseRepositoryGenerator:
    return DatabaseRepositoryGenerator(output_dir=root)


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    gen = _gen(tmp_path)
    result = gen.generate("Order", fields_str="total:float", dry_run=True)

    assert not (tmp_path / "out" / "order_repository.py").exists()
    assert (tmp_path / "out" / "order_repository.py") in result.files_created


def test_force_overwrites_existing(tmp_path: Path) -> None:
    out_file = tmp_path / "out" / "order_repository.py"
    out_file.parent.mkdir(parents=True)
    out_file.write_text("stale")
    gen = _gen(tmp_path)

    result = gen.generate("Order", force=True)

    assert "repository" in out_file.read_text().lower()
    assert out_file in result.files_overwritten


def test_default_skip_keeps_original(tmp_path: Path) -> None:
    out_file = tmp_path / "out" / "order_repository.py"
    out_file.parent.mkdir(parents=True)
    out_file.write_text("original")
    gen = _gen(tmp_path)

    result = gen.generate("Order")

    assert out_file.read_text() == "original"
    assert out_file in result.files_skipped
