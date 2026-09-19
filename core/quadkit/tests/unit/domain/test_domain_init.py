"""Tests for domain/__init__ module."""

import pytest


class TestDomainLazyImports:
    """Tests for domain module lazy imports — core domain exports only."""

    def test_lazy_import_domain_model(self) -> None:
        """Test lazy import of DomainModel."""
        from quadkit.domain import DomainModel

        assert DomainModel is not None

    def test_lazy_import_value_object(self) -> None:
        """Test lazy import of ValueObject."""
        from quadkit.domain import ValueObject

        assert ValueObject is not None

    def test_lazy_import_entity(self) -> None:
        """Test lazy import of Entity."""
        from quadkit.domain import Entity

        assert Entity is not None

    def test_lazy_import_id(self) -> None:
        """Test lazy import of ID."""
        from quadkit.domain import ID

        assert ID is not None

    def test_lazy_import_create_model(self) -> None:
        """Test lazy import of create_model."""
        from quadkit.domain import create_model

        assert callable(create_model)

    def test_lazy_import_domain_error(self) -> None:
        """Test lazy import of DomainError (sourced from contracts)."""
        from quadkit.domain import DomainError

        assert DomainError is not None

    def test_lazy_import_field_error(self) -> None:
        """Test lazy import of FieldError (sourced from contracts)."""
        from quadkit.domain import FieldError

        assert FieldError is not None

    def test_lazy_import_unit_of_work_error(self) -> None:
        """Test lazy import of UnitOfWorkError (sourced from contracts)."""
        from quadkit.domain import UnitOfWorkError

        assert UnitOfWorkError is not None

    def test_lazy_import_validation_error(self) -> None:
        """Test lazy import of ValidationError (sourced from contracts)."""
        from quadkit.domain import ValidationError

        assert ValidationError is not None

    def test_lazy_import_aggregate_root(self) -> None:
        """Test lazy import of AggregateRoot."""
        from quadkit.domain import AggregateRoot

        assert AggregateRoot is not None

    def test_lazy_import_domain_event(self) -> None:
        """Test lazy import of DomainEvent."""
        from quadkit.domain import DomainEvent

        assert DomainEvent is not None

    def test_lazy_import_event_bus(self) -> None:
        """Test lazy import of EventBusProtocol."""
        from quadkit.domain import EventBusProtocol

        assert EventBusProtocol is not None

    def test_lazy_import_repository(self) -> None:
        """Test lazy import of RepositoryProtocol."""
        from quadkit.domain import RepositoryProtocol

        assert RepositoryProtocol is not None

    def test_lazy_import_specification(self) -> None:
        """Test lazy import of SpecificationProtocol."""
        from quadkit.domain import SpecificationProtocol

        assert SpecificationProtocol is not None

    def test_lazy_import_unit_of_work_protocol(self) -> None:
        """Test lazy import of UnitOfWorkProtocol."""
        from quadkit.domain import UnitOfWorkProtocol

        assert UnitOfWorkProtocol is not None

    # ------------------------------------------------------------------
    # Coercion, schema, and field_validator are NOT in domain — verify
    # they are correctly sourced from their canonical modules.
    # ------------------------------------------------------------------

    def test_coerce_str_to_bool_from_canonical_source(self) -> None:
        """coerce_str_to_bool lives in quadkit.validation.engine.coercion."""
        from quadkit.validation.engine.coercion import coerce_str_to_bool

        assert callable(coerce_str_to_bool)

    def test_coerce_to_bool_from_canonical_source(self) -> None:
        """coerce_to_bool lives in quadkit.validation.engine.coercion."""
        from quadkit.validation.engine.coercion import coerce_to_bool

        assert callable(coerce_to_bool)

    def test_coerce_field_value_from_canonical_source(self) -> None:
        """coerce_field_value lives in quadkit.validation.engine.coercion."""
        from quadkit.validation.engine.coercion import coerce_field_value

        assert callable(coerce_field_value)

    def test_bool_true_from_canonical_source(self) -> None:
        """BOOL_TRUE lives in quadkit.validation.engine.coercion."""
        from quadkit.validation.engine.coercion import BOOL_TRUE

        assert isinstance(BOOL_TRUE, frozenset)

    def test_bool_false_from_canonical_source(self) -> None:
        """BOOL_FALSE lives in quadkit.validation.engine.coercion."""
        from quadkit.validation.engine.coercion import BOOL_FALSE

        assert isinstance(BOOL_FALSE, frozenset)

    def test_build_json_schema_from_canonical_source(self) -> None:
        """build_json_schema lives in quadkit.serialization.schema."""
        from quadkit.serialization.schema import build_json_schema

        assert callable(build_json_schema)

    def test_field_validator_from_canonical_source(self) -> None:
        """field_validator lives in quadkit.validation."""
        from quadkit.validation import field_validator

        assert callable(field_validator)


class TestDomainDir:
    """Tests for domain.__dir__()."""

    def test_dir_includes_lazy_imports(self) -> None:
        """Test __dir__ returns all lazy import keys."""
        from quadkit import domain

        d = dir(domain)
        assert "DomainModel" in d
        assert "ValueObject" in d
        assert "Entity" in d

    def test_all_in_dir_are_in_all(self) -> None:
        """Test __all__ matches __dir__."""
        from quadkit import domain

        assert set(dir(domain)) == set(domain.__all__)

    def test_coerce_symbols_not_in_domain_dir(self) -> None:
        """Coercion helpers must not appear in domain.__dir__."""
        from quadkit import domain

        purged = {
            "BOOL_FALSE",
            "BOOL_TRUE",
            "coerce_str_to_bool",
            "coerce_to_bool",
            "coerce_field_value",
            "build_json_schema",
            "python_type_to_json_schema",
            "field_validator",
            "DomainProvider",
        }
        for symbol in purged:
            assert symbol not in dir(domain), f"{symbol} must not be in domain.__dir__"


class TestDomainAttributeError:
    """Tests for domain module error handling."""

    def test_raises_attribute_error_for_unknown(self) -> None:
        """Test that unknown attributes raise AttributeError."""
        from quadkit import domain

        with pytest.raises(AttributeError, match="has no attribute"):
            domain.nonexistent_attribute  # noqa: B018

    def test_raises_attribute_error_for_purged_coerce(self) -> None:
        """Coercion symbols removed from domain raise AttributeError."""
        from quadkit import domain

        with pytest.raises(AttributeError):
            domain.coerce_str_to_bool  # noqa: B018
