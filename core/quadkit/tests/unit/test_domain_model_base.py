"""Tests for the DomainModel init machinery (via create_model, which builds
init=False dataclasses so DomainModel.__init__ runs) and the
Pydantic-compatible API on explicit @dataclass subclasses."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

import pytest

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.domain.models.base import DomainModel
from quadkit.domain.models.factory import create_model
from quadkit.validation.schema import field_validator, model_validator

# ── create_model builds: DomainModel.__init__ is the live path ────────────


def _User(**kw: Any) -> Any:
    User = create_model("User", name=(str, ...), age=(int, 0))
    return User(**kw)


def test_init_with_values_and_defaults() -> None:
    m = _User(name="a", age=3)
    assert m.name == "a"
    assert m.age == 3

    d = _User(name="b")
    assert d.age == 0


def test_missing_required_field_raises_validation_error() -> None:
    User = create_model("User", name=(str, ...))
    with pytest.raises(ValidationError) as excinfo:
        User()  # type: ignore[call-arg]

    errors = excinfo.value.errors
    assert len(errors) == 1
    assert errors[0].field == "name"


def test_default_factory_fields() -> None:
    Model = create_model("Model", items=(list, lambda: []))  # noqa: PIE807 — non-type callable means default_factory
    a = Model()
    b = Model()
    a.items.append("x")
    assert b.items == []  # independent factory instances


def test_id_field_auto_generated() -> None:
    Model = create_model("WithId", id=(str, ...), name=(str, "n"))
    m = Model(id=None)
    assert isinstance(m.id, str)
    assert len(m.id) > 0

    m2 = Model(id="keep-me")
    assert m2.id == "keep-me"


def test_noneable_id_stays_none() -> None:
    Model = create_model("OptId", id=(str | None, None))
    m = Model()
    assert m.id is None


def test_extra_kwargs_become_attributes() -> None:
    m = _User(name="a", unexpected=42)
    assert m.unexpected == 42
    assert "unexpected" not in type(m).__dataclass_fields__


def test_scalar_coercion() -> None:
    # Coercion runs in the env-var direction (str -> numeric).
    m = _User(name="a", age="7")
    assert m.age == 7


# ── Constraint validation via the Field-conversion auto-dataclass path ────
#
# A non-@dataclass subclass of a dataclass DomainModel base (with pydantic
# Field() annotations) is auto-converted at class-creation and gets
# @dataclass(init=False) applied at first instantiation — so
# DomainModel.__init__ (coercion + constraints + validators) runs.


@dataclass(init=False)
class _ConfigBase(DomainModel):
    pass


def test_numeric_constraints() -> None:
    from pydantic import Field

    class Constrained(_ConfigBase):
        age: int = Field(default=0, gt=0, lt=120)

    Constrained(age=50)  # valid
    assert Constrained(age=50).age == 50
    with pytest.raises(ValueError, match="greater than 0"):
        Constrained(age=0)
    with pytest.raises(ValueError, match="less than 120"):
        Constrained(age=120)


def test_string_constraints() -> None:
    from pydantic import Field

    class Code(_ConfigBase):
        code: str = Field(default="", min_length=2, max_length=5, pattern=r"[A-Z]{2,5}")

    Code(code="AB")  # valid
    with pytest.raises(ValueError, match="at least 2"):
        Code(code="A")
    with pytest.raises(ValueError, match="at most 5"):
        Code(code="ABCDEF")
    with pytest.raises(ValueError, match="pattern"):
        Code(code="ab")


def test_ge_le_constraints() -> None:
    from pydantic import Field

    class Range(_ConfigBase):
        value: int = Field(default=5, ge=1, le=10)

    Range(value=1)
    Range(value=10)
    with pytest.raises(ValueError, match="greater than or equal"):
        Range(value=0)
    with pytest.raises(ValueError, match="less than or equal"):
        Range(value=11)


def test_constraints_skip_none_values() -> None:
    from pydantic import Field

    class Nullable(_ConfigBase):
        n: int | None = Field(default=None, gt=0)

    assert Nullable(n=None).n is None


def test_field_validators_before_and_after() -> None:
    from pydantic import Field

    class Validated(_ConfigBase):
        code: str = Field(default="")

        @field_validator("code", mode="before")
        @classmethod
        def _strip(cls, value: Any) -> Any:
            return str(value).strip()

        @field_validator("code")
        @classmethod
        def _upper(cls, value: Any) -> Any:
            return value.upper()

    m = Validated(code="  abc  ")
    assert m.code == "ABC"


def test_model_validators_before_and_after() -> None:
    from pydantic import Field

    class Validated(_ConfigBase):
        value: str = Field(default="")

        @model_validator(mode="before")
        @classmethod
        def _before(cls, kwargs: dict[str, Any]) -> dict[str, Any]:
            if "value" in kwargs:
                kwargs["value"] = str(kwargs["value"]).strip()
            return kwargs

        @model_validator(mode="after")
        def _after(self: Any) -> Any:
            self.value = self.value.upper()
            return self

    m = Validated(value="  hello  ")
    assert m.value == "HELLO"


# ── Pydantic-compatible API (explicit @dataclass subclasses) ──────────────


def test_model_dump_and_exclusions() -> None:
    @dataclass
    class M(DomainModel):
        name: str
        count: int = 0

    m = M(name="a", count=2)
    assert m.model_dump() == {"name": "a", "count": 2}
    assert m.model_dump(exclude={"count"}) == {"name": "a"}
    assert m.model_dump(include={"name"}) == {"name": "a"}


def test_model_dump_json_roundtrip() -> None:
    @dataclass
    class M(DomainModel):
        name: str
        count: int = 0

    m = M(name="json", count=1)
    data = m.model_dump_json()
    assert isinstance(data, str)

    restored = M.model_validate_json(data)
    assert restored.name == "json"
    assert restored.count == 1


def test_model_validate_with_coercion() -> None:
    @dataclass
    class M(DomainModel):
        name: str
        count: int = 0

    m = M.model_validate({"name": 42, "count": "9"})
    assert isinstance(m, M)
    assert m.name == "42"
    assert m.count == 9


def test_model_copy_shallow_deep_and_update() -> None:
    @dataclass
    class M(DomainModel):
        name: str
        count: int = 0

    m = M(name="orig", count=1)

    shallow = m.model_copy()
    assert shallow.name == "orig"
    assert shallow is not m

    updated = m.model_copy(update={"name": "new"})
    assert updated.name == "new"
    assert updated.count == 1

    deep = m.model_copy(deep=True)
    assert deep.model_dump() == m.model_dump()


def test_model_json_schema() -> None:
    @dataclass
    class M(DomainModel):
        name: str

    schema = M.model_json_schema()
    assert isinstance(schema, dict)
    assert "name" in str(schema)


def test_model_extra() -> None:
    @dataclass
    class M(DomainModel):
        name: str

    m = M(name="a")
    extra = m.model_extra
    assert extra is None or isinstance(extra, dict)


def test_repr_str_eq() -> None:
    @dataclass
    class M(DomainModel):
        name: str
        count: int = 0

    a = M(name="x", count=1)
    b = M(name="x", count=1)
    c = M(name="y", count=1)

    assert a == b
    assert a != c
    assert a != "not a model"
    assert "x" in repr(a)
    assert str(a) == repr(a)
    with pytest.raises(TypeError):
        hash(a)


def test_model_rebuild_is_noop() -> None:
    @dataclass
    class M(DomainModel):
        name: str

    M.model_rebuild()  # must not raise


def test_model_config_classvar() -> None:
    @dataclass
    class M(DomainModel):
        name: str

    assert isinstance(M.model_config, dict)


# ── Pydantic Field() conversion ───────────────────────────────────────────


def test_pydantic_field_conversion_required_and_default() -> None:
    from pydantic import Field

    @dataclass
    class WithPydanticField(DomainModel):
        required_thing: str = Field(...)
        optional_thing: str = Field(default="dflt")
        titled: str = Field(default="t", title="Titled", description="A title")

    f = WithPydanticField.__dataclass_fields__
    assert f["required_thing"].default is dataclasses.MISSING
    assert f["optional_thing"].default == "dflt"
    assert f["titled"].metadata.get("title") == "Titled"
    assert f["titled"].metadata.get("description") == "A title"

    m = WithPydanticField(required_thing="v")
    assert m.optional_thing == "dflt"


def test_pydantic_field_constraints_into_metadata() -> None:
    from pydantic import Field

    @dataclass
    class Constrained(DomainModel):
        value: int = Field(default=5, gt=0, lt=10)

    meta = Constrained.__dataclass_fields__["value"].metadata
    assert meta.get("gt") == 0
    assert meta.get("lt") == 10


# ── create_model error handling ───────────────────────────────────────────


def test_create_model_rejects_bad_field_spec() -> None:
    with pytest.raises(TypeError, match="must be a 2-tuple"):
        create_model("Bad", name=str)  # type: ignore[arg-type]


def test_create_model_rejects_unsupported_base() -> None:
    with pytest.raises(TypeError, match="unsupported base"):
        create_model("Bad", __base__=object, name=(str, ...))
