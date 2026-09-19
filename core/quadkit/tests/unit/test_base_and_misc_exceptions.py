"""Tests for base, config, execution, feature flags, middleware, and provider exceptions."""

from quadkit.contracts.constants import DOCS_BASE_URL
from quadkit.contracts.exceptions import ConfigurationError, QuadkitError
from quadkit.contracts.exceptions.execution import (
    PipelineExecutionError,
    PipelineStepError,
)
from quadkit.contracts.exceptions.feature_flags import FeatureFlagError
from quadkit.contracts.exceptions.middleware import MiddlewareGuardError
from quadkit.contracts.exceptions.provider import (
    ModuleCycleError,
    ModuleDuplicateError,
    ModuleError,
    ModuleExportError,
    ModuleImportError,
    ModuleVisibilityError,
    ProviderError,
)


class TestQuadkitErrorBase:
    """Tests for QuadkitError base class."""

    def test_inherits_from_exception(self) -> None:
        """QuadkitError inherits from Exception."""
        assert issubclass(QuadkitError, Exception)

    def test_default_code(self) -> None:
        """QuadkitError has default _code."""
        exc = QuadkitError()
        assert exc._code == "QK_ERR_CORE_001"

    def test_default_message(self) -> None:
        """QuadkitError has default message."""
        exc = QuadkitError()
        assert exc.message == "An internal error occurred"

    def test_custom_message(self) -> None:
        """QuadkitError accepts custom message."""
        exc = QuadkitError(message="Custom error")
        assert exc.message == "Custom error"

    def test_details_default_to_empty_dict(self) -> None:
        """QuadkitError details defaults to empty dict."""
        exc = QuadkitError()
        assert exc.details == {}

    def test_custom_details(self) -> None:
        """QuadkitError accepts custom details."""
        exc = QuadkitError(details={"key": "value"})
        assert exc.details == {"key": "value"}

    def test_hint_defaults_to_none(self) -> None:
        """QuadkitError hint defaults to None."""
        exc = QuadkitError()
        assert exc.hint is None

    def test_custom_hint(self) -> None:
        """QuadkitError accepts custom hint."""
        exc = QuadkitError(hint="Try again")
        assert exc.hint == "Try again"

    def test_cause_defaults_to_none(self) -> None:
        """QuadkitError cause defaults to None."""
        exc = QuadkitError()
        assert exc.cause is None

    def test_custom_cause(self) -> None:
        """QuadkitError accepts custom cause."""
        original = ValueError("original")
        exc = QuadkitError(cause=original)
        assert exc.cause is original

    def test_docs_url_property(self) -> None:
        """QuadkitError has docs_url property."""
        exc = QuadkitError()
        assert exc.docs_url == f"{DOCS_BASE_URL}/reference/errors/QK_ERR_CORE_001"

    def test_to_dict(self) -> None:
        """QuadkitError.to_dict() serializes to dict."""
        exc = QuadkitError(message="Test", details={"key": "value"})
        d = exc.to_dict()
        assert d["message"] == "Test"
        assert d["details"] == {"key": "value"}

    def test_to_dict_includes_hint(self) -> None:
        """QuadkitError.to_dict() includes hint when present."""
        exc = QuadkitError(message="Test", hint="Fix it")
        d = exc.to_dict()
        assert d["hint"] == "Fix it"

    def test_with_details(self) -> None:
        """QuadkitError.with_details() returns new exception."""
        exc = QuadkitError(message="Test", details={"a": 1})
        exc2 = exc.with_details(b=2)
        assert exc2.details == {"a": 1, "b": 2}
        assert exc2.message == "Test"

    def test_with_hint(self) -> None:
        """QuadkitError.with_hint() returns new exception."""
        exc = QuadkitError(message="Test")
        exc2 = exc.with_hint("Try again")
        assert exc2.hint == "Try again"
        assert exc2.message == "Test"

    def test_with_cause(self) -> None:
        """QuadkitError.with_cause() returns new exception."""
        exc = QuadkitError(message="Test")
        original = ValueError("original")
        exc2 = exc.with_cause(original)
        assert exc2.cause is original


class TestConfigurationError:
    """Tests for ConfigurationError."""

    def test_has_code(self) -> None:
        """ConfigurationError has _code."""
        exc = ConfigurationError()
        assert exc._code == "QK_ERR_CFG_001"

    def test_validation_errors_default_to_empty(self) -> None:
        """ConfigurationError validation_errors defaults to empty list."""
        exc = ConfigurationError()
        assert exc.validation_errors == []

    def test_issues_default_to_empty(self) -> None:
        """ConfigurationError issues defaults to empty list."""
        exc = ConfigurationError()
        assert exc.issues == []


class TestPipelineExecutionError:
    """Tests for PipelineExecutionError."""

    def test_has_code(self) -> None:
        """PipelineExecutionError has _code."""
        exc = PipelineExecutionError(step_name="test", error=ValueError("fail"))
        assert exc._code == "QK_ERR_PIPE_001"

    def test_stores_step_name(self) -> None:
        """PipelineExecutionError stores step_name."""
        exc = PipelineExecutionError(step_name="validate", error=ValueError("fail"))
        assert exc.step_name == "validate"

    def test_stores_error(self) -> None:
        """PipelineExecutionError stores error."""
        original = ValueError("fail")
        exc = PipelineExecutionError(step_name="test", error=original)
        assert exc.error is original


class TestPipelineStepError:
    """Tests for PipelineStepError."""

    def test_has_code(self) -> None:
        """PipelineStepError has _code."""
        exc = PipelineStepError()
        assert exc._code == "QK_ERR_PIPE_002"


class TestFeatureFlagError:
    """Tests for FeatureFlagError."""

    def test_has_code(self) -> None:
        """FeatureFlagError has _code."""
        exc = FeatureFlagError()
        assert exc._code == "QK_ERR_FEAT_001"


class TestMiddlewareGuardError:
    """Tests for MiddlewareGuardError."""

    def test_inherits_from_quadkit_error(self) -> None:
        """MiddlewareGuardError inherits from QuadkitError."""
        assert issubclass(MiddlewareGuardError, QuadkitError)

    def test_guard_defaults_to_none(self) -> None:
        """MiddlewareGuardError guard defaults to None."""
        exc = MiddlewareGuardError()
        assert exc.guard is None

    def test_can_specify_guard(self) -> None:
        """MiddlewareGuardError can specify guard."""
        exc = MiddlewareGuardError(guard="AdminGuard")
        assert exc.guard == "AdminGuard"


class TestProviderError:
    """Tests for ProviderError."""

    def test_has_code(self) -> None:
        """ProviderError has _code."""
        exc = ProviderError()
        assert exc._code == "QK_ERR_PROV_001"


class TestModuleError:
    """Tests for ModuleError."""

    def test_has_code(self) -> None:
        """ModuleError has _code."""
        exc = ModuleError()
        assert exc._code == "QK_ERR_MOD_001"


class TestModuleImportError:
    """Tests for ModuleImportError."""

    def test_has_code(self) -> None:
        """ModuleImportError has _code."""
        exc = ModuleImportError()
        assert exc._code == "QK_ERR_MOD_002"

    def test_can_specify_module_name(self) -> None:
        """ModuleImportError can specify module_name."""
        exc = ModuleImportError(module_name="UserModule")
        assert exc.details["module"] == "UserModule"

    def test_can_specify_missing_import(self) -> None:
        """ModuleImportError can specify missing_import."""
        exc = ModuleImportError(missing_import="AuthModule")
        assert exc.details["missing_import"] == "AuthModule"

    def test_can_specify_available_modules(self) -> None:
        """ModuleImportError can specify available_modules."""
        exc = ModuleImportError(available_modules=["A", "B"])
        assert exc.details["available_modules"] == ["A", "B"]


class TestModuleExportError:
    """Tests for ModuleExportError."""

    def test_has_code(self) -> None:
        """ModuleExportError has _code."""
        exc = ModuleExportError()
        assert exc._code == "QK_ERR_MOD_003"


class TestModuleCycleError:
    """Tests for ModuleCycleError."""

    def test_has_code(self) -> None:
        """ModuleCycleError has _code."""
        exc = ModuleCycleError()
        assert exc._code == "QK_ERR_MOD_004"

    def test_can_specify_cycle(self) -> None:
        """ModuleCycleError can specify cycle."""
        exc = ModuleCycleError(cycle=["A", "B", "C"])
        assert exc.details["cycle"] == ["A", "B", "C"]


class TestModuleVisibilityError:
    """Tests for ModuleVisibilityError."""

    def test_has_code(self) -> None:
        """ModuleVisibilityError has _code."""
        exc = ModuleVisibilityError()
        assert exc._code == "QK_ERR_MOD_005"

    def test_can_specify_consumer_and_provider(self) -> None:
        """ModuleVisibilityError can specify consumer and provider modules."""
        exc = ModuleVisibilityError(
            consumer_module="WebModule",
            provider_module="DbModule",
            service_type="UserRepository",
        )
        assert exc.details["consumer_module"] == "WebModule"
        assert exc.details["provider_module"] == "DbModule"
        assert exc.details["service_type"] == "UserRepository"


class TestModuleDuplicateError:
    """Tests for ModuleDuplicateError."""

    def test_has_code(self) -> None:
        """ModuleDuplicateError has _code."""
        exc = ModuleDuplicateError()
        assert exc._code == "QK_ERR_MOD_006"

    def test_can_specify_module_name(self) -> None:
        """ModuleDuplicateError can specify module_name."""
        exc = ModuleDuplicateError(module_name="UserModule")
        assert exc.details["module"] == "UserModule"
