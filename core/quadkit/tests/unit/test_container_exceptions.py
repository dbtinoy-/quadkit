"""Tests for container/DI exceptions from contracts."""

from quadkit.contracts.exceptions import (
    CircularDependencyError,
    ContainerBuildError,
    ContainerError,
    ContainerValidationError,
    DependencyError,
    QuadkitError,
    ProtocolValidationError,
    RegistrationError,
    ScopedResolutionError,
    UnresolvableDependencyError,
)


class TestContainerExceptionHierarchy:
    """Tests for container exception inheritance."""

    def test_all_inherit_from_quadkit_error(self) -> None:
        """All container exceptions inherit from QuadkitError."""
        assert issubclass(ContainerError, QuadkitError)
        assert issubclass(DependencyError, QuadkitError)
        assert issubclass(CircularDependencyError, QuadkitError)
        assert issubclass(UnresolvableDependencyError, QuadkitError)
        assert issubclass(RegistrationError, QuadkitError)
        assert issubclass(ContainerBuildError, QuadkitError)
        assert issubclass(ProtocolValidationError, QuadkitError)
        assert issubclass(ContainerValidationError, QuadkitError)
        assert issubclass(ScopedResolutionError, QuadkitError)

    def test_container_error_is_base(self) -> None:
        """ContainerError is base for container exceptions."""
        assert issubclass(DependencyError, ContainerError)
        assert issubclass(RegistrationError, ContainerError)
        assert issubclass(ContainerBuildError, ContainerError)

    def test_dependency_error_is_container_error(self) -> None:
        """DependencyError inherits from ContainerError."""
        assert issubclass(CircularDependencyError, DependencyError)
        assert issubclass(UnresolvableDependencyError, DependencyError)
        assert issubclass(ScopedResolutionError, UnresolvableDependencyError)


class TestContainerErrorCodes:
    """Tests for container exception error codes."""

    def test_container_error_has_code(self) -> None:
        """ContainerError has _code attribute."""
        exc = ContainerError()
        assert hasattr(exc, "_code")
        assert exc._code == "QK_ERR_DI_001"

    def test_dependency_error_has_code(self) -> None:
        """DependencyError has _code attribute."""
        exc = DependencyError()
        assert exc._code == "QK_ERR_DI_002"

    def test_circular_dependency_error_has_code(self) -> None:
        """CircularDependencyError has _code attribute."""
        exc = CircularDependencyError()
        assert exc._code == "QK_ERR_DI_003"

    def test_registration_error_has_code(self) -> None:
        """RegistrationError has _code attribute."""
        exc = RegistrationError()
        assert exc._code == "QK_ERR_DI_005"

    def test_container_build_error_has_code(self) -> None:
        """ContainerBuildError has _code attribute."""
        exc = ContainerBuildError()
        assert exc._code == "QK_ERR_DI_006"

    def test_protocol_validation_error_has_code(self) -> None:
        """ProtocolValidationError has _code attribute."""
        exc = ProtocolValidationError()
        assert exc._code == "QK_ERR_DI_007"

    def test_container_validation_error_has_code(self) -> None:
        """ContainerValidationError has _code attribute."""
        exc = ContainerValidationError(issues=[])
        assert exc._code == "QK_ERR_DI_008"

    def test_scoped_resolution_error_has_code(self) -> None:
        """ScopedResolutionError has _code attribute."""
        exc = ScopedResolutionError()
        assert exc._code == "QK_ERR_DI_009"


class TestCircularDependencyError:
    """Tests for CircularDependencyError hints."""

    def test_has_default_hint(self) -> None:
        """CircularDependencyError has default hint."""
        exc = CircularDependencyError()
        assert hasattr(exc, "hint")
        assert "constructor parameters" in exc.hint

    def test_can_override_hint(self) -> None:
        """CircularDependencyError hint can be overridden."""
        exc = CircularDependencyError(hint="Custom hint")
        assert exc.hint == "Custom hint"


class TestUnresolvableDependencyError:
    """Tests for UnresolvableDependencyError."""

    def test_can_specify_dependency(self) -> None:
        """Can specify the unresolvable dependency."""
        exc = UnresolvableDependencyError(dependency="UserService")
        assert "dependency" in exc.details
        assert exc.details["dependency"] == "UserService"

    def test_has_default_hint(self) -> None:
        """UnresolvableDependencyError has default hint."""
        exc = UnresolvableDependencyError()
        assert hasattr(exc, "hint")
        assert "registered in a Provider" in exc.hint


class TestRegistrationError:
    """Tests for RegistrationError."""

    def test_has_default_hint(self) -> None:
        """RegistrationError has default hint."""
        exc = RegistrationError()
        assert hasattr(exc, "hint")
        assert "Provider.register()" in exc.hint


class TestContainerValidationError:
    """Tests for ContainerValidationError."""

    def test_stores_issues(self) -> None:
        """ContainerValidationError stores validation issues."""
        issues = ["missing dependency A", "circular reference B"]
        exc = ContainerValidationError(issues=issues)
        assert exc.issues == issues

    def test_includes_issues_in_details(self) -> None:
        """ContainerValidationError includes issues in details."""
        issues = ["issue1", "issue2"]
        exc = ContainerValidationError(issues=issues)
        assert "issues" in exc.details
        assert exc.details["issues"] == issues

    def test_message_includes_issues(self) -> None:
        """ContainerValidationError message includes issues."""
        issues = ["missing dependency A", "circular reference B"]
        exc = ContainerValidationError(issues=issues)
        assert "missing dependency A" in str(exc)
        assert "circular reference B" in str(exc)

    def test_custom_message(self) -> None:
        """ContainerValidationError accepts custom message."""
        issues = ["issue1"]
        exc = ContainerValidationError(issues=issues, message="Custom error")
        assert "Custom error" in str(exc)


class TestScopedResolutionError:
    """Tests for ScopedResolutionError."""

    def test_can_specify_service(self) -> None:
        """Can specify the scoped service that failed."""
        exc = ScopedResolutionError(service="RequestService")
        assert "service" in exc.details
        assert exc.details["service"] == "RequestService"

    def test_has_default_message(self) -> None:
        """ScopedResolutionError has descriptive default message."""
        exc = ScopedResolutionError()
        assert "scoped service" in str(exc).lower()
        assert "active scope" in str(exc).lower()
