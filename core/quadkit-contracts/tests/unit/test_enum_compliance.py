"""Verify all enumeration-like classes use enum.Enum.

This test suite ensures that the entire Quadkit Framework follows
the pattern of using enum.Enum (or str, Enum) for all classes that
define enumerable sets of string constants.

The requirement is enforced in the architectural guidelines:
- Use enum.Enum for enumeration types
- Use class X(str, Enum): to enable string comparisons
- All enum member values must be explicitly defined
"""

from __future__ import annotations

import ast
import inspect
from enum import Enum
from pathlib import Path

import pytest

# Import all representative enums to verify they're proper Enum classes
from quadkit.contracts.ai.governance import AuditEventType
from quadkit.contracts.ai.session import SessionStatus
from quadkit.contracts.ai.types import ModelCapability, ModelProvider
from quadkit.contracts.core.concurrency_enums import ConcurrencyStrategy
from quadkit.contracts.core.health import HealthStatus
from quadkit.contracts.core.provider import Lifecycle, ProviderPriority
from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.contracts.data.vector.enums import DistanceMetric, IndexState, IndexType
from quadkit.contracts.infra.resilience.enums import CircuitState, RetryStrategy


class TestEnumComplianceImportable:
    """Test that all documented enum classes are importable and properly typed."""

    def test_audit_event_type_is_enum(self) -> None:
        """Verify AuditEventType is a proper Enum."""
        assert inspect.isclass(AuditEventType)
        assert issubclass(AuditEventType, Enum)
        assert hasattr(AuditEventType, "CREATED")
        assert isinstance(AuditEventType.CREATED, AuditEventType)

    def test_model_provider_is_enum(self) -> None:
        """Verify ModelProvider is a proper Enum."""
        assert inspect.isclass(ModelProvider)
        assert issubclass(ModelProvider, Enum)
        assert hasattr(ModelProvider, "OPENAI")

    def test_model_capability_is_enum(self) -> None:
        """Verify ModelCapability is a proper Enum."""
        assert inspect.isclass(ModelCapability)
        assert issubclass(ModelCapability, Enum)

    def test_session_status_is_enum(self) -> None:
        """Verify SessionStatus is a proper Enum."""
        assert inspect.isclass(SessionStatus)
        assert issubclass(SessionStatus, Enum)

    def test_provider_priority_is_enum(self) -> None:
        """Verify ProviderPriority is a proper Enum."""
        assert inspect.isclass(ProviderPriority)
        assert issubclass(ProviderPriority, Enum)
        assert ProviderPriority.CRITICAL.value == 0

    def test_lifecycle_is_enum(self) -> None:
        """Verify Lifecycle is a proper Enum."""
        assert inspect.isclass(Lifecycle)
        assert issubclass(Lifecycle, Enum)

    def test_health_status_is_enum(self) -> None:
        """Verify HealthStatus is a proper Enum."""
        assert inspect.isclass(HealthStatus)
        assert issubclass(HealthStatus, Enum)

    def test_distance_metric_is_enum(self) -> None:
        """Verify DistanceMetric is a proper Enum."""
        assert inspect.isclass(DistanceMetric)
        assert issubclass(DistanceMetric, Enum)
        assert DistanceMetric.COSINE.value == "cosine"

    def test_index_type_is_enum(self) -> None:
        """Verify IndexType is a proper Enum."""
        assert inspect.isclass(IndexType)
        assert issubclass(IndexType, Enum)

    def test_index_state_is_enum(self) -> None:
        """Verify IndexState is a proper Enum."""
        assert inspect.isclass(IndexState)
        assert issubclass(IndexState, Enum)

    def test_circuit_state_is_enum(self) -> None:
        """Verify CircuitState is a proper Enum."""
        assert inspect.isclass(CircuitState)
        assert issubclass(CircuitState, Enum)

    def test_retry_strategy_is_enum(self) -> None:
        """Verify RetryStrategy is a proper Enum."""
        assert inspect.isclass(RetryStrategy)
        assert issubclass(RetryStrategy, Enum)

    def test_concurrency_strategy_is_enum(self) -> None:
        """Verify ConcurrencyStrategy is a proper Enum."""
        assert inspect.isclass(ConcurrencyStrategy)
        assert issubclass(ConcurrencyStrategy, Enum)

    def test_sql_dialect_is_enum(self) -> None:
        """Verify SQLDialect is a proper Enum."""
        assert inspect.isclass(SQLDialect)
        assert issubclass(SQLDialect, Enum)


class TestEnumComplianceCoreLibrary:
    """Test that quadkit.contracts defines NO bare string constant classes."""

    @pytest.fixture
    def contracts_path(self) -> Path:
        """Get path to quadkit.contracts source."""
        import quadkit.contracts

        module_file = quadkit.contracts.__file__
        assert module_file is not None
        return Path(module_file).parent

    @staticmethod
    def _find_bare_string_classes(path: Path) -> list[tuple[Path, str, int]]:
        """Find all bare string constant classes in a directory.

        Returns list of (filepath, classname, lineno) tuples.
        """
        bare_classes = []

        for py_file in path.rglob("*.py"):
            try:
                with open(py_file, "r") as f:
                    content = f.read()
                tree = ast.parse(content)
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it's a bare class (no bases)
                    bases = list(node.bases)
                    if len(bases) == 0:
                        # Check if it only contains string assignments
                        has_only_constants = True
                        has_string_constants = False

                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                # Check if it's assigning a string constant
                                if isinstance(item.value, ast.Constant) and isinstance(
                                    item.value.value, str
                                ):
                                    has_string_constants = True
                            elif isinstance(item, ast.Pass):
                                continue
                            elif isinstance(item, ast.Expr) and isinstance(
                                item.value, ast.Constant
                            ):
                                # Docstring
                                continue
                            else:
                                # Not just a constant
                                has_only_constants = False
                                break

                        if has_string_constants and has_only_constants:
                            bare_classes.append((py_file, node.name, node.lineno))

        return bare_classes

    def test_no_bare_string_classes(self, contracts_path: Path) -> None:
        """Verify that quadkit.contracts contains NO bare string constant classes.

        All enum-like definitions MUST use either:
        - class X(str, Enum): ...
        - class X(Enum): ...
        - class X(StrEnum): ... (Python 3.11+)
        """
        bare_classes = self._find_bare_string_classes(contracts_path)

        message = f"Found {len(bare_classes)} bare string constant classes in contracts:\n"
        for filepath, classname, lineno in sorted(bare_classes):
            relative = filepath.relative_to(contracts_path.parent)
            message += f"  {relative}:{lineno} - {classname}\n"
        message += "\nAll enum-like classes MUST use Enum (see architectural guidelines)."

        assert len(bare_classes) == 0, message


class TestEnumValueAccess:
    """Test that enum values are accessible and properly typed."""

    def test_enum_values_are_strings(self) -> None:
        """Verify that str-based enums return string values."""
        # Test a few representative enums
        assert isinstance(DistanceMetric.COSINE.value, str)
        assert isinstance(Lifecycle.REGISTER.value, str)

    def test_enum_iteration(self) -> None:
        """Verify that enums can be iterated."""
        metrics = list(DistanceMetric)
        assert len(metrics) > 0
        assert all(isinstance(m, DistanceMetric) for m in metrics)

    def test_enum_membership(self) -> None:
        """Verify that enum members can be checked."""
        assert DistanceMetric.COSINE in DistanceMetric
        assert ProviderPriority.CRITICAL in ProviderPriority


class TestEnumDocumentation:
    """Verify that enums have proper docstrings."""

    def test_enum_has_docstring(self) -> None:
        """Verify that key enums have module-level documentation."""
        # Just verify the classes are documented
        assert DistanceMetric.__doc__ is not None
        assert ProviderPriority.__doc__ is not None
        assert HealthStatus.__doc__ is not None


# Parametrized tests for comprehensive coverage
@pytest.mark.parametrize(
    "enum_class",
    [
        AuditEventType,
        ModelProvider,
        ModelCapability,
        SessionStatus,
        ProviderPriority,
        Lifecycle,
        HealthStatus,
        DistanceMetric,
        IndexType,
        IndexState,
        CircuitState,
        RetryStrategy,
        ConcurrencyStrategy,
        SQLDialect,
    ],
    ids=lambda e: e.__name__,
)
def test_all_enums_are_proper_enums(enum_class: type[Enum]) -> None:
    """Verify all documented enum classes inherit from Enum."""
    assert inspect.isclass(enum_class)
    assert issubclass(enum_class, Enum)
    assert len(list(enum_class)) > 0, f"{enum_class.__name__} has no members"


@pytest.mark.parametrize(
    "enum_class",
    [
        ModelProvider,
        ModelCapability,
        DistanceMetric,
        Lifecycle,
    ],
    ids=lambda e: e.__name__,
)
def test_str_enums_support_string_values(enum_class: type[Enum]) -> None:
    """Verify that string-based enums have string values."""
    for member in enum_class:
        # These should work for StrEnum or (str, Enum)
        assert isinstance(member.value, str)
