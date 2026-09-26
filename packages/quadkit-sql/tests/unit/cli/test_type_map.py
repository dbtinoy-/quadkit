"""Tests for the shared SQL generator field-type vocabulary."""

from __future__ import annotations

from quadkit.sql.cli.generators.type_map import (
    DEFAULT_PY_TYPE,
    DEFAULT_SA_TYPE,
    PY_TYPES,
    SA_TYPES,
    extra_dependencies,
    python_type,
    render_imports,
    sa_type,
)


def test_every_python_type_has_a_matching_column_type() -> None:
    """A field type must be resolvable for both the model and the table."""
    assert set(PY_TYPES) == set(SA_TYPES)


def test_unknown_types_fall_back() -> None:
    """Unrecognised field types degrade to text rather than raising."""
    assert python_type("not-a-type") == DEFAULT_PY_TYPE
    assert sa_type("not-a-type") == DEFAULT_SA_TYPE


def test_numeric_types_avoid_decimal() -> None:
    """Decimal-ish types map to float for SQLite and JSON compatibility."""
    for field_type in ("decimal", "numeric", "money"):
        assert python_type(field_type) == "float"
    assert sa_type("decimal") == "Float"


def test_structured_types_map_to_real_columns() -> None:
    """Structured types get structured columns, not String(255)."""
    assert sa_type("json") == "JSON"
    assert sa_type("date") == "Date"
    assert sa_type("time") == "Time"
    assert sa_type("bytes") == "LargeBinary"


def test_render_imports_merges_base_and_annotation_imports() -> None:
    """Base imports are always present and each module appears once."""
    lines = render_imports(["date", "time", "dict[str, Any]", "EmailStr"])

    assert "from datetime import date, datetime, time, timezone" in lines
    assert "from pydantic import AnyHttpUrl" not in lines
    assert "from pydantic import BaseModel, ConfigDict, EmailStr, Field" in lines
    assert "from typing import Any" in lines
    assert len(lines) == len(set(line.split(" import ")[0] for line in lines))


def test_render_imports_without_annotations() -> None:
    """A plain entity needs only the base imports."""
    assert render_imports([]) == [
        "from datetime import datetime, timezone",
        "from pydantic import BaseModel, ConfigDict, Field",
    ]


def test_extra_dependencies_only_for_constrained_types() -> None:
    """Only annotations with an external requirement are reported."""
    assert extra_dependencies(["EmailStr"]) == ("email-validator",)
    assert extra_dependencies(["str", "dict[str, Any]"]) == ()
    assert extra_dependencies(["EmailStr", "AnyHttpUrl"]) == ("email-validator",)
