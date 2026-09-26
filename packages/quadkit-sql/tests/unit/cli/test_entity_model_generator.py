"""Field-type mapping and DTO shape tests for EntityModelGenerator."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.sql.cli.generators.entity_model import EntityModelGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _render(tmp_path: Path, fields: str | None = None) -> str:
    """Generate a model module inside an anchored src-layout project.

    Args:
        tmp_path: Scratch project root.
        fields: Optional ``--fields`` specification string.

    Returns:
        The rendered model source.
    """
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "models"
    out.mkdir(parents=True, exist_ok=True)
    result = EntityModelGenerator(output_dir=out).generate("Note", fields)
    return Path(result.files_created[0]).read_text()


def _annotation(source: str, cls: str, field: str) -> str:
    """Return the declared annotation for a field on one of the DTOs."""
    body = source.split(f"class {cls}(BaseModel):", 1)[1]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{field}:"):
            return stripped
    raise AssertionError(f"{cls} has no field {field!r}")


def test_known_types_are_preserved(tmp_path: Path) -> None:
    """Core scalar types keep their natural Python annotations."""
    source = _render(tmp_path, "title:str,count:int,ratio:float,ok:bool,when:datetime")
    assert _annotation(source, "Note", "title") == "title: str"
    assert _annotation(source, "Note", "count") == "count: int"
    assert _annotation(source, "Note", "ratio") == "ratio: float"
    assert _annotation(source, "Note", "ok") == "ok: bool"
    assert _annotation(source, "Note", "when") == "when: datetime"


@pytest.mark.parametrize(
    ("field_type", "expected"),
    [
        ("decimal", "float"),
        ("numeric", "float"),
        ("money", "float"),
        ("date", "date"),
        ("time", "time"),
        ("json", "dict[str, Any]"),
        ("bytes", "bytes"),
        ("email", "EmailStr"),
        ("url", "AnyHttpUrl"),
        ("ipv4", "IPvAnyAddress"),
        ("bigint", "int"),
        ("timestamp", "datetime"),
    ],
)
def test_extended_types_map_to_real_annotations(
    tmp_path: Path, field_type: str, expected: str
) -> None:
    """Field types outside the original map no longer collapse to ``str``."""
    source = _render(tmp_path, f"value:{field_type}")
    assert _annotation(source, "Note", "value") == f"value: {expected}"


def test_unknown_type_falls_back_to_str(tmp_path: Path) -> None:
    """An unrecognised field type still degrades to text, not a hard failure."""
    source = _render(tmp_path, "value:notarealtype")
    assert _annotation(source, "Note", "value") == "value: str"


def test_required_imports_are_emitted_and_merged(tmp_path: Path) -> None:
    """Constrained annotations bring their imports, each module once."""
    source = _render(tmp_path, "day:date,at:time,meta:json,email:email,site:url")
    assert "from datetime import date, datetime, time, timezone" in source
    assert "from typing import Any" in source
    assert "from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field" in (
        source
    )
    # Each module appears on exactly one import line.
    assert len([line for line in source.splitlines() if line.startswith("from datetime")]) == 1
    assert len([line for line in source.splitlines() if line.startswith("from pydantic")]) == 1


def test_email_field_declares_its_dependency(tmp_path: Path) -> None:
    """``EmailStr`` is unusable without ``email-validator``, so say so."""
    source = _render(tmp_path, "email:email")
    assert "Requires: email-validator" in source


def test_dependency_note_absent_without_constrained_types(tmp_path: Path) -> None:
    """Plain entities carry no extra install requirement."""
    source = _render(tmp_path, "title:str")
    assert "Requires:" not in source


def test_datetime_is_not_coerced_to_str_on_payloads(tmp_path: Path) -> None:
    """Create payloads keep real datetimes so Pydantic parses them."""
    source = _render(tmp_path, "when:datetime")
    assert _annotation(source, "NoteCreate", "when") == "when: datetime"


def test_update_is_a_consistent_partial_patch(tmp_path: Path) -> None:
    """Every Update field is optional with a ``None`` default."""
    source = _render(tmp_path, "title:str,count:int,when:datetime,meta:json")
    assert _annotation(source, "NoteUpdate", "title") == "title: str | None = None"
    assert _annotation(source, "NoteUpdate", "count") == "count: int | None = None"
    assert _annotation(source, "NoteUpdate", "when") == "when: datetime | None = None"
    assert _annotation(source, "NoteUpdate", "meta") == "meta: dict[str, Any] | None = None"


def test_optional_entity_fields_stay_optional(tmp_path: Path) -> None:
    """``?`` on a field keeps it optional on the entity and Create payload."""
    source = _render(tmp_path, "title:str?")
    assert _annotation(source, "Note", "title") == "title: str | None = None"
    assert _annotation(source, "NoteCreate", "title") == "title: str | None = None"


def test_reserved_fields_are_not_duplicated(tmp_path: Path) -> None:
    """Audit columns are generated once even when requested in ``--fields``."""
    source = _render(tmp_path, "id:str,created_at:datetime,title:str")
    assert source.count("    id: str = Field(") == 1
    assert source.count("    created_at: datetime = Field(") == 1
