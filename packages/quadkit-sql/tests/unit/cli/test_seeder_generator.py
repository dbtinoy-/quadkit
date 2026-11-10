"""SeederGenerator sample-row behavior around foreign keys.

A seed must never invent a foreign-key value: with FK enforcement on,
a fabricated UUID fails at insert. A nullable FK samples as ``None``;
a required FK suppresses the sample row entirely.
"""

from __future__ import annotations

from pathlib import Path

from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec
from quadkit.sql.cli.generators.seeder import SeederGenerator

FABRICATED_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _render(tmp_path: Path, fields: tuple[FieldSpec, ...]) -> str:
    gen = SeederGenerator(output_dir=tmp_path)
    gen.generate(
        "post",
        entity_spec=EntitySpec(name="post", table_name="posts", fields=fields),
    )
    return (tmp_path / "post.py").read_text()


def test_required_foreign_key_suppresses_the_sample_row(tmp_path: Path) -> None:
    content = _render(
        tmp_path,
        (
            FieldSpec(name="author_id", type="uuid", fk="authors.id"),
            FieldSpec(name="title", type="str"),
        ),
    )
    assert "SEED_DATA: list[dict[str, Any]] = []" in content
    assert "must never invent foreign-key values" in content
    assert FABRICATED_UUID not in content
    compile(content, "post.py", "exec")


def test_nullable_foreign_key_samples_as_none(tmp_path: Path) -> None:
    content = _render(
        tmp_path,
        (
            FieldSpec(name="author_id", type="uuid", fk="authors.id", required=False),
            FieldSpec(name="title", type="str"),
        ),
    )
    assert '"author_id": None,' in content
    assert '"title": "Sample Post Title",' in content
    assert FABRICATED_UUID not in content
    compile(content, "post.py", "exec")


def test_field_without_foreign_key_keeps_the_sample_row(tmp_path: Path) -> None:
    content = _render(tmp_path, (FieldSpec(name="title", type="str"),))
    assert '"title": "Sample Post Title",' in content
    assert "SEED_DATA: list[dict[str, Any]] = [\n" in content
    compile(content, "post.py", "exec")
