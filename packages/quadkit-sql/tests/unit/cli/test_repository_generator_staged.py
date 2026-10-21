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


def test_outcome_methods_return_result_and_probes_stay_inside(tmp_path: Path) -> None:
    """R6 pin: get/update/delete return `Result`; absence is an `Err` value,
    never `None`/bool; `list` stays raw (an empty page is a value)."""
    gen = _gen(tmp_path)
    gen.generate("Order", fields_str="total:float")
    content = (tmp_path / "out" / "order_repository.py").read_text()

    assert "from quadkit.result import Err, Ok, Result" in content
    assert (
        "from quadkit.contracts.exceptions import NotFoundError" in content
    )
    assert "def get(self, key: str) -> Result[dict[str, Any], NotFoundError]:" in content
    assert ") -> Result[dict[str, Any], NotFoundError]:" in content  # update
    assert "def delete(self, key: str) -> Result[bool, NotFoundError]:" in content
    assert "def list(self, limit: int = 50) -> list[dict[str, Any]]:" in content
    # And the old sentinel-ful law is gone — the translation happens here,
    # inside the repository, exactly once per outcome.
    assert "-> dict[str, Any] | None" not in content
    assert '"""Delete by primary key; *bool* answers' not in content


def test_exception_source_is_a_context_option(tmp_path: Path) -> None:
    """Modular apps name their own error class; the CLI default is contracts."""
    gen = _gen(tmp_path)
    gen.generate(
        "Order",
        fields_str="total:float",
        not_found_error="OrderNotFoundError",
        exceptions_module="shop_api.modules.users.exceptions",
    )
    content = (tmp_path / "out" / "order_repository.py").read_text()
    assert (
        "from shop_api.modules.users.exceptions import OrderNotFoundError" in content
    )
    assert "def get(self, key: str) -> Result[dict[str, Any], OrderNotFoundError]:" in content
    assert 'OrderNotFoundError(f"Order not found with id: {key}")' in content


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
