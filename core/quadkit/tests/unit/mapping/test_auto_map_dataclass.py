"""``auto_map`` against a dataclass destination — and against a row-shaped source.

The mapper's documented job is "match field names, let the destination construct
itself". For a ``@dataclass`` destination that job did not happen:

* ``get_type_hints(dest_type.__init__)`` is the fallback when the destination has
  no Pydantic ``model_fields``. ``@dataclass`` generates ``__init__`` with the
  class's annotations copied onto its parameters, and under
  ``from __future__ import annotations`` those are *strings* — so a single
  ``if TYPE_CHECKING: from datetime import datetime`` (the house style of most
  models in this repository) made the call raise ``NameError`` before a single
  field was matched.

``quadkit.domain.DomainModel`` is such a destination, and a repository hydrating
one from a row is exactly the shape this covers: an object whose attributes are
the columns (``vars(obj)``), including SQLAlchemy's ``_sa_instance_state``, which
is private bookkeeping rather than a field.

The destination here is a plain dataclass rather than a ``DomainModel`` on
purpose: the mapper must work for any dataclass, and the domain model's own
coercion and validators are covered in ``tests/unit/domain/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from quadkit.mapping.config import MappingConfig
from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.mapping.exceptions import MappingExecutionError, MappingNotFoundError

if TYPE_CHECKING:
    from uuid import UUID


class OrmRow:
    """A source object with no ``model_dump``/``asdict`` — ``vars()`` is the seam."""

    def __init__(self) -> None:
        self.id = "i-1"
        self.plugin_id = "p-1"
        self.created_at = "2026-10-14T01:02:03"
        self.config = {"retries": 3}
        self._sa_instance_state = object()


@dataclass
class Install:
    """Destination whose annotations name types imported only for the checker."""

    id: str = ""
    plugin_id: str = ""
    installed_by: UUID | None = None  # noqa: F821 — TYPE_CHECKING import
    config: dict[str, Any] = field(default_factory=dict)


class TestDataclassDestination:
    """A dataclass destination has to be introspectable, not an error."""

    @pytest.fixture
    def mapper(self) -> ObjectMapperImpl:
        return ObjectMapperImpl()

    def test_every_declared_field_is_matched(self, mapper: ObjectMapperImpl) -> None:
        """The regression: an unresolvable annotation left *all* fields unmatched."""
        result = mapper.auto_map(OrmRow(), Install)

        assert result.id == "i-1"
        assert result.plugin_id == "p-1"
        assert result.config == {"retries": 3}

    def test_it_returns_the_destination_type(self, mapper: ObjectMapperImpl) -> None:
        assert isinstance(mapper.auto_map(OrmRow(), Install), Install)

    def test_private_source_attributes_are_not_fields(
        self, mapper: ObjectMapperImpl
    ) -> None:
        """``_sa_instance_state`` is bookkeeping: it must not land in ``__dict__``."""
        result = mapper.auto_map(OrmRow(), Install)

        assert "_sa_instance_state" not in vars(result)

    def test_missing_source_fields_fall_back_to_defaults(
        self, mapper: ObjectMapperImpl
    ) -> None:
        result = mapper.auto_map({"id": "i-2"}, Install)

        assert result.id == "i-2"
        assert result.config == {}
        assert result.installed_by is None

    def test_nested_values_reach_the_destination_constructor(
        self, mapper: ObjectMapperImpl
    ) -> None:
        """A dict-valued field is handed to the destination, not flattened."""
        result = mapper.auto_map({"config": {"a": 1, "nested": {"on": True}}}, Install)

        assert result.config == {"a": 1, "nested": {"on": True}}


class TestMappingConfigKnobs:
    """``MappingConfig`` fields have to be honoured — a declared knob that does
    nothing is worse than no knob: the caller believes the check ran.
    """

    def test_unknown_fields_are_dropped_by_default(self) -> None:
        mapper = ObjectMapperImpl()

        assert mapper.auto_map({"id": "i-3", "tenant": "t-1"}, Install).id == "i-3"

    def test_ignore_unknown_disabled_raises(self) -> None:
        mapper = ObjectMapperImpl(config=MappingConfig(ignore_unknown=False))

        with pytest.raises(MappingExecutionError, match="tenant"):
            mapper.auto_map({"id": "i-3", "tenant": "t-1"}, Install)

    def test_case_insensitive_matching_maps_to_the_declared_name(self) -> None:
        mapper = ObjectMapperImpl(config=MappingConfig(case_sensitive=False))

        result = mapper.auto_map({"ID": "i-4", "PLUGIN_ID": "p-4"}, Install)

        assert result.id == "i-4"
        assert result.plugin_id == "p-4"

    def test_case_sensitive_is_the_default(self) -> None:
        mapper = ObjectMapperImpl()

        assert mapper.auto_map({"ID": "i-5"}, Install).id == ""

    def test_map_or_auto_refuses_to_guess_when_auto_map_is_off(self) -> None:
        mapper = ObjectMapperImpl(config=MappingConfig(auto_map=False))

        with pytest.raises(MappingNotFoundError):
            mapper.map_or_auto(OrmRow(), Install)

    def test_map_or_auto_still_falls_back_by_default(self) -> None:
        mapper = ObjectMapperImpl()

        assert mapper.map_or_auto(OrmRow(), Install).plugin_id == "p-1"
