"""Exception contract surface: config redaction, components, provider."""

from __future__ import annotations

from quadkit.contracts.core.config import ConfigIssue
from quadkit.contracts.exceptions.components import (
    ComponentConnectionError,
    ComponentError,
    KeyExistsError,
    KeyNotFoundError,
    PubSubError,
)
from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.contracts.exceptions.provider import (
    ModuleCycleError,
    ModuleDuplicateError,
    ModuleError,
    ModuleExportError,
    ModuleImportError,
    ModuleVisibilityError,
    ProviderError,
)


class _PydanticLikeError(Exception):
    """Mimics pydantic ValidationError with .errors() returning dicts."""

    def __init__(self, errors: list[dict]) -> None:
        super().__init__("pydantic-style")
        self._errors = errors

    def errors(self) -> list[dict]:
        return self._errors


class _FieldErr:
    def __init__(self, field: str, message: str, code: str = "bad") -> None:
        self.field = field
        self.message = message
        self.code = code
        self.input = "raw-value"


class TestConfigurationError:
    def test_basics(self) -> None:
        e = ConfigurationError("bad config")
        assert e.validation_errors == []
        assert e.issues == []
        assert ConfigurationError._code == "QK_ERR_CFG_001"

    def test_from_contracts_validation_error(self) -> None:
        from quadkit.contracts.exceptions.domain import FieldError

        ve = ValidationError(errors=[FieldError("db.url", "must be a URL")])
        e = ConfigurationError.from_validation_error(ve)
        assert e.validation_errors == [
            {
                "field": "db.url",
                "message": "must be a URL",
                "type": "INVALID",
                "value": "(not set)",
            }
        ]
        assert "db.url: must be a URL" in str(e)

    def test_from_contracts_validation_error_add_error(self) -> None:
        ve = ValidationError()
        ve.add_error("name", "required")
        e = ConfigurationError.from_validation_error(ve)
        assert e.validation_errors[0]["field"] == "name"
        assert e.validation_errors[0]["message"] == "required"

    def test_from_pydantic_style(self) -> None:
        pe = _PydanticLikeError(
            [
                {
                    "loc": ("db", "port"),
                    "msg": "field required",
                    "type": "missing",
                    "input": None,
                }
            ]
        )
        e = ConfigurationError.from_validation_error(pe)
        assert e.validation_errors[0]["field"] == "db → port"
        assert e.validation_errors[0]["type"] == "missing"
        assert e.validation_errors[0]["value"] == "(not set)"

    def test_secret_redaction(self) -> None:
        pe = _PydanticLikeError(
            [
                {
                    "loc": ("db", "password"),
                    "msg": "too short",
                    "type": "value_error",
                    "input": "hunter2",
                }
            ]
        )
        e = ConfigurationError.from_validation_error(pe)
        assert e.validation_errors[0]["value"] == "***"
        assert "hunter2" not in str(e)

    def test_long_value_truncated(self) -> None:
        long_value = "x" * 200
        pe = _PydanticLikeError(
            [
                {
                    "loc": ("name",),
                    "msg": "bad",
                    "type": "t",
                    "input": long_value,
                }
            ]
        )
        e = ConfigurationError.from_validation_error(pe)
        assert e.validation_errors[0]["value"].endswith("...")
        assert len(e.validation_errors[0]["value"]) == 80

    def test_no_errors_attribute(self) -> None:
        e = ConfigurationError.from_validation_error(ValueError("plain"))
        assert "plain" in str(e)

    def test_from_issues(self) -> None:
        issues = [
            ConfigIssue(field="a", message="err a", severity="error"),
            ConfigIssue(field="b", message="warn b", severity="warning"),
            ConfigIssue(field="c", message="err c", severity="error"),
        ]
        e = ConfigurationError.from_issues(issues)
        assert "a: err a" in str(e)
        assert "c: err c" in str(e)
        assert "warn b" not in str(e)
        assert len(e.issues) == 3  # warnings kept on the object


class TestComponentExceptions:
    def test_component_error_details(self) -> None:
        e = ComponentError(
            "failed",
            component_type="queue",
            driver_type="rabbitmq",
            details={"extra": 1},
        )
        assert e.component_type == "queue"
        assert e.driver_type == "rabbitmq"
        assert e.details["component_type"] == "queue"
        assert e.details["driver_type"] == "rabbitmq"
        assert e.details["extra"] == 1

    def test_component_error_no_details(self) -> None:
        e = ComponentError("failed")
        assert e.component_type is None
        assert e.driver_type is None

    def test_key_errors(self) -> None:
        nf = KeyNotFoundError("k1")
        assert nf.key == "k1"
        assert "k1" in str(nf)
        ex = KeyExistsError("k2")
        assert ex.key == "k2"
        assert "k2" in str(ex)

    def test_pubsub_topic(self) -> None:
        e = PubSubError("down", topic="orders")
        assert "orders" in str(e.details.get("topic", "")) or e.details.get(
            "topic"
        ) == "orders"

    def test_connection_error_hierarchy(self) -> None:
        e = ComponentConnectionError("conn refused")
        assert isinstance(e, ComponentError)
        from quadkit.contracts.exceptions import InfrastructureError

        assert isinstance(e, InfrastructureError)


class TestProviderExceptions:
    def test_provider_error(self) -> None:
        e = ProviderError()
        assert "Provider error" in str(e)
        assert "QK_ERR_PROV_001" in str(e)
        assert ProviderError._code == "QK_ERR_PROV_001"

    def test_module_error_defaults(self) -> None:
        assert "Module error" in str(ModuleError())
        assert ModuleError._code == "QK_ERR_MOD_001"

    def test_module_import_error_details(self) -> None:
        e = ModuleImportError(
            module_name="a",
            missing_import="b",
            available_modules=["x", "y"],
        )
        assert e.details["module"] == "a"
        assert e.details["missing_import"] == "b"
        assert e.details["available_modules"] == ["x", "y"]

    def test_module_error_subclasses(self) -> None:
        for cls, code in [
            (ModuleExportError, "QK_ERR_MOD_003"),
            (ModuleCycleError, "QK_ERR_MOD_004"),
            (ModuleVisibilityError, "QK_ERR_MOD_005"),
            (ModuleDuplicateError, "QK_ERR_MOD_006"),
        ]:
            assert issubclass(cls, ModuleError)
            assert cls._code == code, cls

    def test_module_visibility_error(self) -> None:
        e = ModuleVisibilityError(
            consumer_module="a",
            provider_module="b",
            service_type="C",
        )
        assert e.details["consumer_module"] == "a"
        assert e.details["provider_module"] == "b"
        assert e.details["service_type"] == "C"

    def test_module_cycle_and_export_errors(self) -> None:
        c = ModuleCycleError(cycle=["a", "b", "a"])
        assert c.details["cycle"] == ["a", "b", "a"]
        x = ModuleExportError(missing_export="Svc", registered_types=["Other"])
        assert x.details["missing_export"] == "Svc"
        assert x.details["registered_types"] == ["Other"]
        d = ModuleDuplicateError(module_name="m")
        assert d.details["module"] == "m"
