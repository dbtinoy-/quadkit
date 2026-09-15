"""Tests for di/extensions/validator module - ProtocolValidator."""

import pytest
from typing import Protocol

from quadkit.di.extensions.validator import (
    ProtocolValidator,
    validate_protocol,
    validate_protocol_static,
)


class MyProtocol(Protocol):
    """Test protocol with required methods."""

    def do_something(self) -> str: ...
    value: str


class GoodImplementation:
    """Implementation that satisfies MyProtocol."""

    value: str = "test"

    def do_something(self) -> str:
        return "done"


class BadImplementationMissingMethod:
    """Implementation missing a required method."""

    value: str = "test"


class BadImplementationWrongType:
    """Implementation with wrong type for attribute."""

    value: str = "test"

    def do_something(self) -> int:
        return 123


class TestValidateProtocol:
    """Tests for validate_protocol function."""

    def test_validate_protocol_success(self) -> None:
        """Test validate_protocol with valid implementation."""
        impl = GoodImplementation()
        validate_protocol(impl, MyProtocol)  # Should not raise

    def test_validate_protocol_missing_method(self) -> None:
        """Test validate_protocol raises on missing method."""
        impl = BadImplementationMissingMethod()
        with pytest.raises(TypeError, match="missing member"):
            validate_protocol(impl, MyProtocol)

    def test_validate_protocol_wrong_type(self) -> None:
        """Test validate_protocol works with implementation that has different return type."""
        # Note: The validator checks for callable, not return type, so this passes
        impl = BadImplementationWrongType()
        validate_protocol(impl, MyProtocol)  # Should not raise - methods are callable


class TestValidateProtocolStatic:
    """Tests for validate_protocol_static function."""

    def test_validate_protocol_static_success(self) -> None:
        """Test validate_protocol_static with valid class."""
        validate_protocol_static(GoodImplementation, MyProtocol)  # Should not raise

    def test_validate_protocol_static_missing_method(self) -> None:
        """Test validate_protocol_static raises on missing method."""
        with pytest.raises(TypeError, match="missing member"):
            validate_protocol_static(BadImplementationMissingMethod, MyProtocol)


class TestProtocolValidator:
    """Tests for ProtocolValidator class."""

    def test_init(self) -> None:
        """Test ProtocolValidator initialization."""
        validator = ProtocolValidator()
        assert validator is not None

    def test_validate_registration_non_protocol(self) -> None:
        """Test validate_registration skips non-protocol types."""

        class MyService:
            pass

        validator = ProtocolValidator()
        validator.validate_registration(MyService, MyService)  # Should not raise

    def test_validate_registration_with_protocol_success(self) -> None:
        """Test validate_registration with protocol and valid implementation."""
        validator = ProtocolValidator()
        validator.validate_registration(MyProtocol, GoodImplementation)  # Should not raise

    def test_validate_registration_with_protocol_failure(self) -> None:
        """Test validate_registration with protocol and invalid implementation."""
        validator = ProtocolValidator()
        with pytest.raises(Exception):  # ProtocolValidationError
            validator.validate_registration(MyProtocol, BadImplementationMissingMethod)

    def test_validate_registration_with_factory(self) -> None:
        """Test validate_registration skips factory functions."""
        validator = ProtocolValidator()
        my_factory = lambda: GoodImplementation()
        validator.validate_registration(MyProtocol, my_factory)  # Should not raise

    def test_validate_resolution_non_protocol_success(self) -> None:
        """Test validate_resolution with non-protocol type."""
        validator = ProtocolValidator()

        class MyService:
            pass

        service = MyService()
        validator.validate_resolution(service, MyService)  # Should not raise

    def test_validate_resolution_non_protocol_failure(self) -> None:
        """Test validate_resolution with wrong type."""
        validator = ProtocolValidator()

        class MyService:
            pass

        class OtherService:
            pass

        service = OtherService()
        with pytest.raises(Exception):  # ProtocolValidationError
            validator.validate_resolution(service, MyService)

    def test_validate_resolution_protocol_success(self) -> None:
        """Test validate_resolution with protocol and valid instance."""
        validator = ProtocolValidator()
        impl = GoodImplementation()
        validator.validate_resolution(impl, MyProtocol)  # Should not raise

    def test_validate_resolution_protocol_failure(self) -> None:
        """Test validate_resolution with protocol and invalid instance."""
        validator = ProtocolValidator()
        impl = BadImplementationMissingMethod()
        with pytest.raises(Exception):  # ProtocolValidationError
            validator.validate_resolution(impl, MyProtocol)

    def test_is_protocol_with_protocol(self) -> None:
        """Test _is_protocol returns True for Protocol."""
        validator = ProtocolValidator()
        assert validator._is_protocol(MyProtocol) is True

    def test_is_protocol_with_regular_class(self) -> None:
        """Test _is_protocol returns False for regular class."""
        validator = ProtocolValidator()

        class MyService:
            pass

        assert validator._is_protocol(MyService) is False

    def test_is_protocol_with_non_class(self) -> None:
        """Test _is_protocol returns False for non-class."""
        validator = ProtocolValidator()
        assert validator._is_protocol("not a class") is False
        assert validator._is_protocol(123) is False
        assert validator._is_protocol(None) is False

    def test_normalize_type_plain(self) -> None:
        """Test _normalize_type with plain type."""
        validator = ProtocolValidator()
        result = validator._normalize_type(str)
        assert result is str

    def test_normalize_type_with_protocol(self) -> None:
        """Test _normalize_type with Protocol returns None."""
        validator = ProtocolValidator()
        result = validator._normalize_type(MyProtocol)
        # Protocol doesn't have get_origin so it returns as-is
        assert result is MyProtocol


class TestProtocolValidatorEdgeCases:
    """Edge case tests for ProtocolValidator."""

    def test_validate_registration_with_instance(self) -> None:
        """Test validate_registration with instance instead of class."""
        validator = ProtocolValidator()
        impl = GoodImplementation()
        validator.validate_registration(MyProtocol, impl)  # Should not raise

    def test_validate_registration_with_method(self) -> None:
        """Test validate_registration with bound method skips."""
        validator = ProtocolValidator()

        class MyService:
            def my_method(self):
                pass

        service = MyService()
        validator.validate_registration(MyProtocol, service.my_method)  # Should not raise


class TestProtocolWithAnnotations:
    """Tests for protocols with annotations."""

    def test_protocol_with_annotations(self) -> None:
        """Test protocol with __annotations__."""

        class AnnotatedProtocol(Protocol):
            name: str

            def do_work(self) -> None: ...

        class GoodAnnotated:
            name: str = "test"

            def do_work(self) -> None:
                pass

        validate_protocol(GoodAnnotated(), AnnotatedProtocol)  # Should not raise


class TestValidateProtocolStaticAnnotationOnlyAttributes:
    """Regression tests: PEP 526 annotation-only attributes must not cause
    :func:`validate_protocol_static` to falsely reject conformant classes.

    Bug: a class that declares a protocol's required data attribute purely
    via a bare annotation (``name: str``, no class-level default) and
    assigns it per-instance in ``__init__`` — the standard, idiomatic way to
    declare instance attributes — is a *fully conformant* implementation
    (every instance satisfies the protocol). But ``hasattr(cls, name)`` is
    ``False`` for such attributes on the *class* itself, since the name is
    never bound until ``__init__`` runs. The static checker used to rely
    solely on ``hasattr``, so it spuriously rejected these implementations,
    which in turn made DI factory-registration validation
    (``ProtocolValidator.validate_registration`` for typed factories)
    reject perfectly valid bindings and forced call sites to disable
    protocol validation (``validate=False``) entirely to work around it.
    """

    def test_annotation_only_attribute_conforms_statically(self) -> None:
        """A class declaring the attribute only via annotation, assigned in
        __init__, must pass the static check."""

        class AnnotatedOnlyProtocol(Protocol):
            request_id: str | None

            def do_work(self) -> None: ...

        class AnnotatedOnlyImpl:
            request_id: str | None

            def __init__(self, request_id: str | None = None) -> None:
                self.request_id = request_id

            def do_work(self) -> None:
                pass

        # Every instance genuinely satisfies the protocol...
        validate_protocol(AnnotatedOnlyImpl(request_id="abc"), AnnotatedOnlyProtocol)
        # ...so the static (class-level) check must agree.
        validate_protocol_static(AnnotatedOnlyImpl, AnnotatedOnlyProtocol)

    def test_annotation_only_attribute_inherited_from_base_conforms(self) -> None:
        """Annotation-only attributes declared on a base class are also
        recognized by the static check."""

        class AnnotatedOnlyProtocol(Protocol):
            value: int

        class Base:
            value: int

            def __init__(self, value: int) -> None:
                self.value = value

        class Derived(Base):
            pass

        validate_protocol_static(Derived, AnnotatedOnlyProtocol)

    def test_static_check_still_rejects_truly_missing_attribute(self) -> None:
        """An implementation that never declares the attribute at all
        (no annotation, no class value) must still fail."""

        class Proto(Protocol):
            name: str

            def do(self) -> None: ...

        class MissingAttrImpl:
            def do(self) -> None:
                pass

        with pytest.raises(TypeError, match="missing member 'name'"):
            validate_protocol_static(MissingAttrImpl, Proto)

    def test_static_check_still_rejects_missing_method(self) -> None:
        """A required *method* must be present and callable even when the
        implementation has annotation-only data attributes; a bare
        annotation can never satisfy a callable requirement."""

        class Proto(Protocol):
            name: str

            def do(self) -> None: ...

        class MissingMethodImpl:
            name: str

            def __init__(self) -> None:
                self.name = "x"

        with pytest.raises(TypeError, match="missing member 'do'"):
            validate_protocol_static(MissingMethodImpl, Proto)

    def test_factory_registration_with_annotation_only_return_type(self) -> None:
        """The bug's real-world trigger: a DI factory whose return-type
        annotation is a class using annotation-only attributes must pass
        registration-time protocol validation without needing
        ``validate=False``."""

        class ContextProto(Protocol):
            request_id: str | None

            def do_work(self) -> None: ...

        class ContextImpl:
            request_id: str | None

            def __init__(self, request_id: str | None = None) -> None:
                self.request_id = request_id

            def do_work(self) -> None:
                pass

        def factory() -> ContextImpl:
            return ContextImpl(request_id="abc")

        validator = ProtocolValidator()
        validator.validate_registration(ContextProto, factory)  # Should not raise
