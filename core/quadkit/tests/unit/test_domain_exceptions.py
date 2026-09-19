"""Unit tests for domain exceptions."""

import pytest

from quadkit.domain.exceptions import (
    DomainError,
    DomainPolicyViolationError,
    FieldError,
    UnitOfWorkError,
    ValidationError,
)


class TestDomainError:
    def test_inheritance(self) -> None:
        assert issubclass(DomainError, Exception)


class TestFieldError:
    def test_inheritance(self) -> None:
        assert issubclass(FieldError, Exception)


class TestValidationError:
    def test_inheritance(self) -> None:
        assert issubclass(ValidationError, Exception)


class TestUnitOfWorkError:
    def test_inheritance(self) -> None:
        assert issubclass(UnitOfWorkError, Exception)


class TestDomainPolicyViolationError:
    def test_inheritance(self) -> None:
        assert issubclass(DomainPolicyViolationError, Exception)

    def test_code(self) -> None:
        assert DomainPolicyViolationError._code == "QK_ERR_DOM_009"

    def test_policy_name_attribute(self) -> None:
        exc = DomainPolicyViolationError(policy_name="my_policy", message="Violation")
        assert exc.policy_name == "my_policy"

    def test_details_contains_policy_name(self) -> None:
        exc = DomainPolicyViolationError(policy_name="test_policy", message="Failed")
        assert exc.details.get("policy_name") == "test_policy"