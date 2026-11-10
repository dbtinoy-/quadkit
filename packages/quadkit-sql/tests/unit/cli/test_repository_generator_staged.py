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
    """R6 pin: all five CRUD verbs return `Result`; absence is an `Err` value,
    never `None`/bool; success payloads keep their historical shapes."""
    gen = _gen(tmp_path)
    gen.generate("Order", fields_str="total:float")
    content = (tmp_path / "out" / "order_repository.py").read_text()

    assert "from quadkit.result import Err, Ok, Result" in content
    assert (
        "from quadkit.contracts.exceptions import ConflictError, NotFoundError"
        in content
    )
    # Write verbs additionally sign the integrity arm: unique/constraint
    # collisions are expected outcomes (409 ConflictError), not 500s.
    assert ") -> Result[OrderEntity, ConflictError | NotFoundError]:" in content  # create
    assert "def get(self, key: str) -> Result[dict[str, Any], NotFoundError]:" in content
    assert ") -> Result[dict[str, Any], ConflictError | NotFoundError]:" in content  # update
    assert "def delete(self, key: str) -> Result[bool, ConflictError | NotFoundError]:" in content
    assert ") -> Result[list[dict[str, Any]], NotFoundError]:" in content  # list


def test_json_fields_hydrate_on_read(tmp_path: Path) -> None:
    """A `json` field round-trips: providers JSON-encode it on write,
    so the rendered repository parses it back in `_row_to_entity` —
    without that, every JSON column leaks out of reads as a string
    while the entity annotation swears it is a dict."""
    import importlib.util

    gen = _gen(tmp_path)
    gen.generate("SavedSearch", fields_str="name:str,filters:json?")
    path = tmp_path / "out" / "saved_search_repository.py"
    content = path.read_text()
    assert '_JSON_FIELDS = frozenset(["filters"])' in content
    assert "import json as _json" in content

    spec = importlib.util.spec_from_file_location("saved_search_repository", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inner = module._SavedSearchInner(
        provider=object(),
        table_name="saved_searches",
        entity_class=module.SavedSearchEntity,
        key_field="id",
    )
    # The raw row as the driver returns it: JSON text (compact form).
    entity = inner._row_to_entity(
        {"id": "1", "name": "recent", "filters": '{"sort":"desc"}'}
    )
    assert entity.filters == {"sort": "desc"}
    none = inner._row_to_entity({"id": "2", "name": "bare", "filters": None})
    assert none.filters is None


def test_no_json_fields_keeps_plain_row_mapping(tmp_path: Path) -> None:
    """No json fields → no hydration machinery at all (no dead code),
    and the render is unchanged — including whitespace: the plain
    row mapping is followed by exactly two blank lines before the
    repository class, as before the JSON support existed."""
    gen = _gen(tmp_path)
    gen.generate("Order", fields_str="total:float")
    content = (tmp_path / "out" / "order_repository.py").read_text()
    assert "_JSON_FIELDS" not in content
    assert "_json" not in content
    assert "        return self.entity_class(**dict(row))\n\n\nclass " in content
    assert "except DuplicateKeyError:" in content
    assert "except IntegrityError:" in content
    # No foreign keys on this entity: no reference-mapping helper and no
    # 422 arm in the write annotations (the word still appears in prose).
    assert "_reference_error" not in content
    assert "FieldError" not in content
    assert "ValidationError |" not in content
    assert "return Ok(found)" in content
    assert "return Ok([self._inner._serialize_entity(e) for e in entities])" in content
    # And the old sentinel-ful law is gone — the translation happens here,
    # inside the repository, exactly once per outcome.
    assert "async def create(self, data: dict[str, Any]) -> OrderEntity:" not in content
    assert "-> list[dict[str, Any]]:" not in content
    assert "-> dict[str, Any] | None" not in content
    assert "-> bool:" not in content
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
    # Integrity domain errors still come from contracts: only the
    # not-found lineage is app-owned.
    assert "from quadkit.contracts.exceptions import ConflictError" in content
    assert "def get(self, key: str) -> Result[dict[str, Any], OrderNotFoundError]:" in content
    assert ") -> Result[OrderEntity, ConflictError | OrderNotFoundError]:" in content
    assert ") -> Result[list[dict[str, Any]], OrderNotFoundError]:" in content
    assert 'OrderNotFoundError(f"Order not found with id: {key}")' in content


def test_write_only_fields_are_stripped_from_serialized_rows(tmp_path: Path) -> None:
    """A ``!writeonly`` field is stored but stripped from every serialized
    row, and create returns the public shape instead of the raw entity."""
    gen = _gen(tmp_path)
    gen.generate("Account", fields_str="name:str,password_hash:str!writeonly")
    content = (tmp_path / "out" / "account_repository.py").read_text()

    assert '_WRITE_ONLY_FIELDS = frozenset(["password_hash"])' in content
    assert "for write_only in _WRITE_ONLY_FIELDS:" in content
    assert "serialized.pop(write_only, None)" in content
    assert "Result[dict[str, Any], ConflictError | NotFoundError]" in content
    assert "return Ok(self._inner._serialize_entity(found))" in content


def test_foreign_key_fields_render_reference_error_mapping(tmp_path: Path) -> None:
    """A structured FK field gives create/update a field-level 422 arm."""
    from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec

    gen = _gen(tmp_path)
    gen.generate(
        "Post",
        entity_spec=EntitySpec(
            name="post",
            table_name="posts",
            fields=(
                FieldSpec(
                    name="author_id",
                    type="uuid",
                    fk="authors.id",
                    on_delete="restrict",
                    indexed=True,
                ),
                FieldSpec(name="title", type="str"),
            ),
        ),
    )
    content = (tmp_path / "out" / "post_repository.py").read_text()

    assert '"author_id": "authors.id"' in content
    assert "def _reference_error(data: dict[str, Any]) -> ValidationError:" in content
    assert 'code="reference_missing"' in content
    assert "except ForeignKeyError:" in content
    assert (
        ") -> Result[PostEntity, ConflictError | ValidationError | NotFoundError]:"
        in content
    )
    assert (
        "from quadkit.contracts.exceptions import "
        "ConflictError, FieldError, ValidationError, NotFoundError" in content
    )
    compile(content, "post_repository.py", "exec")


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
