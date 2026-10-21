"""Hydration semantics for ``DomainModel`` — the path repositories use.

These pin the contract ``GenericRepository`` depends on when it turns a
database row into an entity: ``Model.model_validate(row)`` must coerce the
scalar types the row carries (ISO timestamps, uuid4-format strings, enum
values), must tolerate a column the model does not declare, and must enforce
the same ``Field(...)`` constraints and validators as direct construction.

Every test here covers a way the old implementation diverged from that
contract, so a regression fails with the reason attached.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from typing import Any
from uuid import UUID

import pytest

from quadkit.domain import DomainModel
from quadkit.validation import Field, field_validator

# ── scalar coercion ──────────────────────────────────────────────────────────


@dataclass
class Row(DomainModel):
    """The shape a `SELECT` hands back after JSON round-tripping the values."""

    id: str = ""
    name: str = ""
    count: int = 0
    ratio: float = 0.0
    active: bool = False
    created_at: datetime.datetime = datetime.datetime(2026, 1, 1)  # noqa: DTZ001
    day: datetime.date = datetime.date(2026, 1, 1)
    trace: UUID | None = None


@dataclass
class Line(DomainModel):
    """A nested model, defined at module scope so hints resolve."""

    sku: str = ""
    qty: int = 0


@dataclass
class Order(DomainModel):
    id: str = ""
    lines: list[Line] = Field(default_factory=list)


def test_model_validate_coerces_iso_timestamps() -> None:
    """A row's ISO timestamp becomes a ``datetime``, not a string."""
    row = Row.model_validate({"created_at": "2026-10-14T01:02:03", "day": "2026-10-14"})
    assert isinstance(row.created_at, datetime.datetime)
    assert row.created_at == datetime.datetime(2026, 10, 14, 1, 2, 3)  # noqa: DTZ001
    assert isinstance(row.day, datetime.date)


def test_model_validate_coerces_scalars_the_way_the_constructor_does() -> None:
    """``model_validate`` and ``Model(**row)`` agree — one guard, one behaviour."""
    row = {"name": 42, "count": "9", "ratio": "1.5", "active": "true",
           "trace": "123e4567-e89b-12d3-a456-426614174000"}
    validated = Row.model_validate(row)
    constructed = Row(**row)
    assert validated == constructed
    assert (validated.name, validated.count, validated.ratio) == ("42", 9, 1.5)
    assert validated.active is True
    assert isinstance(validated.trace, UUID)


def test_model_validate_coerces_nested_models_from_dicts() -> None:
    order = Order.model_validate({"id": "o-1", "lines": [{"sku": "a", "qty": "2"}]})
    assert isinstance(order.lines[0], Line)
    assert order.lines[0].qty == 2


def test_id_declared_as_str_stays_a_string() -> None:
    """The declared annotation wins over "this looks like a UUID"."""
    uid = "123e4567-e89b-12d3-a456-426614174000"
    slugged = Row.model_validate({"id": uid})
    assert slugged.id == uid
    assert isinstance(slugged.id, str)


# ── unknown columns ──────────────────────────────────────────────────────────


def test_model_validate_tolerates_undeclared_columns() -> None:
    """A row that grew a column must not raise ``TypeError``.

    Rows carry whatever the schema has; a domain model that stopped declaring
    one of those columns is a normal evolution, and the extra is retrievable
    (``model_extra``) rather than fatal.
    """
    row = Row.model_validate({"id": "r-1", "name": "n", "tenant_id": "t-9"})
    assert row.name == "n"
    assert row.model_extra == {"tenant_id": "t-9"}


def test_model_dump_hides_private_bookkeeping() -> None:
    """``model_dump`` and ``model_extra`` agree on what an extra is."""
    row = Row.model_validate({"id": "r-1", "tenant_id": "t-9"})
    dumped = row.model_dump(mode="json")
    assert dumped["tenant_id"] == "t-9"
    assert all(not key.startswith("_") for key in dumped)


# ── constraints and validators ───────────────────────────────────────────────


@dataclass
class Constrained(DomainModel):
    name: str = Field(default="abc", min_length=3, max_length=10)
    level: str = "INFO"
    slug: str = Field(default="ok", pattern=r"[a-z]+")

    @field_validator("level")
    @classmethod
    def _known_level(cls, value: Any) -> Any:
        if value not in ("INFO", "WARN", "ERROR"):
            msg = f"unknown level {value!r}"
            raise ValueError(msg)
        return value


def test_constraints_fire_on_construction() -> None:
    """``Field(min_length=...)`` is a check, not documentation.

    ``@dataclass`` regenerates ``__init__``, so the base class's validation
    never ran for the documented model pattern; the guard installed on
    ``__post_init__`` is what makes this raise.
    """
    with pytest.raises(ValueError, match="at least 3 characters"):
        Constrained(name="ab")
    with pytest.raises(ValueError, match="match pattern"):
        Constrained(slug="Not A Slug")


def test_constraints_and_validators_fire_on_model_validate() -> None:
    with pytest.raises(ValueError, match="at least 3 characters"):
        Constrained.model_validate({"name": "ab"})
    with pytest.raises(ValueError, match="unknown level"):
        Constrained.model_validate({"level": "TRACE"})


def test_within_constraints_round_trips() -> None:
    model = Constrained.model_validate({"name": "valid", "level": "WARN"})
    assert model.model_dump(mode="json") == {
        "name": "valid",
        "level": "WARN",
        "slug": "ok",
    }


# ── the repository contract ──────────────────────────────────────────────────


def test_model_dump_matches_hand_written_to_dict() -> None:
    """``model_dump(mode="json")`` reproduces a hand-written ``to_dict``.

    This is the trade an adopting application makes: delete the per-model
    ``to_dict``/``from_dict`` pair and let the framework's serializer produce
    the same bytes, keys in declaration order and datetimes in ISO form.
    """

    @dataclass
    class Manual:
        id: str = "p-1"
        created_at: datetime.datetime = datetime.datetime(2026, 10, 14, 1, 2, 3)  # noqa: DTZ001

        def to_dict(self) -> dict[str, Any]:
            return {"id": self.id, "created_at": self.created_at.isoformat()}

    @dataclass
    class Framework(DomainModel):
        id: str = "p-1"
        created_at: datetime.datetime = datetime.datetime(2026, 10, 14, 1, 2, 3)  # noqa: DTZ001

    manual = Manual().to_dict()
    auto = Framework().model_dump(mode="json")
    assert auto == manual
    assert list(auto) == list(manual)


# ── annotations that exist only for the type checker ─────────────────────────


def test_type_checking_annotations_still_coerce(tmp_path: Any) -> None:
    """A module that imports its annotation types under ``TYPE_CHECKING``.

    ``if TYPE_CHECKING: from datetime import datetime`` leaves nothing behind at
    runtime, so ``get_type_hints`` raises ``NameError`` and the whole class loses
    its types — no coercion, no validation, no schema. That is the house style
    across most of the repository, so the resolver supplies the names the
    coercion engine acts on: ``datetime``, ``date``, ``UUID``, ``Decimal``, plus
    the framework's own ``ConfigDict`` (a base-class annotation).
    """
    import importlib
    import sys

    module_file = tmp_path / "quadkit_tc_module.py"
    module_file.write_text(
        """from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from quadkit.domain import DomainModel

if TYPE_CHECKING:
    from datetime import date, datetime
    from uuid import UUID


@dataclass
class Record(DomainModel):
    id: str = ""
    created_at: datetime | None = None
    day: date | None = None
    trace: UUID | None = None
"""
    )
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("quadkit_tc_module")
        record = module.Record.model_validate(
            {
                "id": "r-1",
                "created_at": "2026-10-14T01:02:03",
                "day": "2026-10-14",
                "trace": "123e4567-e89b-12d3-a456-426614174000",
            }
        )
        assert isinstance(record.created_at, datetime.datetime)
        assert isinstance(record.day, datetime.date)
        assert isinstance(record.trace, UUID)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("quadkit_tc_module", None)


# ── normalising raw column shapes before coercion ────────────────────────────


@dataclass
class StoredRow(DomainModel):
    """A model over a table whose columns are not the field's runtime shape.

    ``stored_at`` is a ``BigInteger`` epoch column and ``payload`` a JSON
    document in a ``Text`` column — the two shapes every ORM-backed schema ends
    up with. Declaring them with ``mode="before"`` is what a validator is for:
    it sees the raw value and hands the engine the type the field declares.
    """

    stored_at: datetime.datetime = datetime.datetime(2026, 1, 1)  # noqa: DTZ001
    payload: dict[str, Any] = field(default_factory=dict)

    @field_validator("stored_at", mode="before")
    @classmethod
    def _epoch_column(cls, value: Any) -> Any:
        if isinstance(value, int):
            return datetime.datetime.fromtimestamp(value, datetime.UTC).replace(tzinfo=None)
        return value

    @field_validator("payload", mode="before")
    @classmethod
    def _json_text_column(cls, value: Any) -> Any:
        from quadkit import serialization

        return serialization.loads(value) if isinstance(value, str) else value


def test_before_validators_run_on_the_generated_init_path() -> None:
    """``Model(**row)`` and ``model_validate(row)`` must agree.

    ``@dataclass`` generates ``__init__``, and the guard it installs into
    ``__post_init__`` used to dispatch only ``mode="after"``. A before-validator
    therefore ran when a repository hydrated through ``model_validate`` and was
    silently skipped when the same row went through the constructor — one model,
    two behaviours, and the skipped one left an epoch integer in a datetime
    field.
    """
    row = {"stored_at": 1_700_000_000, "payload": '{"retries": 3}'}

    built = StoredRow(**row)
    hydrated = StoredRow.model_validate(row)

    assert built.stored_at == datetime.datetime(2023, 11, 14, 22, 13, 20)  # noqa: DTZ001
    assert hydrated.stored_at == built.stored_at
    assert built.payload == {"retries": 3}
    assert hydrated.payload == built.payload


def test_before_validators_see_the_raw_value_not_the_coerced_one() -> None:
    """The hook's contract: raw in, declared type out."""
    seen: list[Any] = []

    @dataclass
    class Watched(DomainModel):
        at: datetime.datetime = datetime.datetime(2026, 1, 1)  # noqa: DTZ001

        @field_validator("at", mode="before")
        @classmethod
        def _watch(cls, value: Any) -> Any:
            seen.append(value)
            return value

    Watched(at="2026-10-14T01:02:03")  # noqa: DTZ001

    assert seen == ["2026-10-14T01:02:03"]


# ── a declared default, and the constraints it may contradict ────────────────


@dataclass
class Contradiction(DomainModel):
    """A declaration that rejects its own default.

    ``Field(default="", min_length=3)`` is a mistake in the *declaration*, and
    the framework's answer is to refuse to construct the model — for a caller
    who omits the field exactly as for one who passes the same value.
    """

    name: str = Field(default="", min_length=3)


@dataclass
class SoundDefault(DomainModel):
    """The ordinary case: a default that satisfies its own constraint."""

    count: int = Field(default=0, ge=0)


def test_a_default_is_not_exempt_from_its_constraint() -> None:
    """Silently accepting the default would let the model violate its own rule.

    A `ge=0` counter with a negative default is a documented invariant that the
    value the model itself supplies breaks — exactly the kind of thing that
    reaches production as a negative counter and a dashboard nobody trusts. The
    two construction paths agree because both check the value the field holds.
    """
    with pytest.raises(ValueError, match="at least 3"):
        Contradiction()
    with pytest.raises(ValueError, match="at least 3"):
        Contradiction.model_validate({})
    with pytest.raises(ValueError, match="at least 3"):
        Contradiction(name="")

    assert Contradiction(name="abc").name == "abc"


def test_a_valid_default_still_constructs() -> None:
    """The check is on the value, not on the fact that it was defaulted."""
    assert SoundDefault().count == 0
    assert SoundDefault.model_validate({}).count == 0


def test_defaults_are_coerced_like_provided_values() -> None:
    """`Model()` and `model_validate({})` must produce the same field types.

    A default or factory that carries a column's storage shape — an ISO string
    where the field is a datetime, a numeric string where the field is an int —
    is normalised on both paths. The generated-`__init__` path always did this
    (the guard coerces whatever it finds); the `DomainModel.__init__` path used
    to assign the raw default, so the same model had different field types
    depending on how it was built.
    """

    @dataclass
    class Stamped(DomainModel):
        at: datetime.datetime = Field(
            default_factory=lambda: "2026-10-14T01:02:03"  # type: ignore[arg-type]
        )
        count: int = Field(default="42")  # type: ignore[arg-type]

    built = Stamped()
    hydrated = Stamped.model_validate({})

    assert built.at == datetime.datetime(2026, 10, 14, 1, 2, 3)  # noqa: DTZ001
    assert hydrated.at == built.at
    assert built.count == 42
    assert hydrated.count == 42
