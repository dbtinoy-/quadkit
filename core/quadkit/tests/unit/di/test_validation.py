"""Tests for ContainerValidator — scope validation exhaustiveness.

Covers FAANG finding:
  M-03: broad except in validate() swallowed TypeError as a warning;
        TypeError from missing type annotations must surface as a validation issue.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.container.validation import ContainerValidator
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.type_hints import TypeHintResolverImpl


def _make_singleton_descriptor(impl: type) -> MagicMock:
    """Build a minimal service descriptor MagicMock for a singleton."""
    descriptor = MagicMock()
    descriptor.service_type = impl
    descriptor.implementation = impl
    descriptor.scope = ServiceScope.SINGLETON
    return descriptor


class TestScopeValidationExhaustiveness:
    def test_type_error_produces_validation_issue_not_silent_skip(self) -> None:
        """Non-unhashable TypeError from get_type_dependencies must appear in validate() issues.

        Before M-03 fix, a TypeError was caught by the broad except and emitted
        only as a logger.warning — the returned ``issues`` list was empty, so
        operators had no visibility into unannotated implementations.

        After the fix, a TypeError that is NOT about an unhashable type surfaces
        as a validation issue entry.
        """

        class UnannotatedService:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(UnannotatedService)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = TypeError(
            "no type hints available"
        )

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert len(issues) == 1, f"Expected 1 issue, got: {issues}"
        assert "UnannotatedService" in issues[0]
        assert "Scope analysis incomplete" in issues[0]

    def test_unhashable_type_error_produces_warning_not_validation_issue(
        self,
    ) -> None:
        """TypeError: unhashable type is a resolver-internal issue, not a user issue.

        It must be logged as a warning and NOT populate the issues list, to avoid
        breaking applications that register instances as type hints (e.g. QuadkitConfig).
        """

        class SomeConfigService:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(SomeConfigService)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = TypeError(
            "unhashable type: 'SomeConfigService'"
        )

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        # unhashable TypeError → warning only; must not appear as a validation issue
        assert issues == []

    def test_attribute_error_produces_warning_not_validation_issue(self) -> None:
        """AttributeError is an infrastructure problem, not a user-facing issue.

        It must be logged as a warning and NOT populate the issues list.
        """

        class SomeService:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(SomeService)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = AttributeError(
            "missing attr"
        )

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        # AttributeError → warning only; must not appear as a validation issue
        assert issues == []

    def test_key_error_produces_warning_not_validation_issue(self) -> None:
        """KeyError during scope resolution must not surface as a user-visible issue."""

        class SomeService:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(SomeService)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = KeyError("missing_key")

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert issues == []

    def test_value_error_produces_warning_not_validation_issue(self) -> None:
        """ValueError during scope resolution must not surface as a user-visible issue."""

        class SomeService:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(SomeService)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = ValueError("bad value")

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert issues == []

    def test_type_error_message_includes_exception_detail(self) -> None:
        """The validation issue text must embed the original TypeError message."""

        class MyFactory:
            pass

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [_make_singleton_descriptor(MyFactory)]

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.side_effect = TypeError(
            "unsupported operand type — cannot introspect"
        )

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert any("unsupported operand type" in issue for issue in issues)

    def test_graph_validate_issues_are_preserved(self) -> None:
        """Issues from registry.validate_graph() must not be discarded."""

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = ["Circular dependency: A → B → A"]
        registry.all.return_value = []

        validator = ContainerValidator(registry, MagicMock(spec=TypeHintResolverImpl))
        issues = validator.validate()

        assert "Circular dependency: A → B → A" in issues

    def test_no_issues_for_well_annotated_singletons(self) -> None:
        """A properly annotated singleton with only singleton deps produces no issues."""

        class DepService:
            pass

        class RootService:
            pass

        dep_descriptor = _make_singleton_descriptor(DepService)
        root_descriptor = _make_singleton_descriptor(RootService)

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [root_descriptor]

        # root depends on DepService which is also SINGLETON
        dep_descriptor.scope = ServiceScope.SINGLETON
        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.return_value = {DepService}
        registry.get.return_value = dep_descriptor

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert issues == []

    def test_scope_violation_detected(self) -> None:
        """Singleton depending on a scoped service must produce a scope-violation issue."""

        class ScopedDep:
            pass

        class SingletonRoot:
            pass

        scoped_descriptor = MagicMock()
        scoped_descriptor.scope = ServiceScope.SCOPED
        scoped_descriptor.service_type = ScopedDep

        root_descriptor = _make_singleton_descriptor(SingletonRoot)

        registry = MagicMock(spec=ServiceRegistry)
        registry.validate_graph.return_value = []
        registry.all.return_value = [root_descriptor]
        registry.get.return_value = scoped_descriptor

        type_hint_resolver = MagicMock(spec=TypeHintResolverImpl)
        type_hint_resolver.get_type_dependencies.return_value = {ScopedDep}

        validator = ContainerValidator(registry, type_hint_resolver)
        issues = validator.validate()

        assert len(issues) == 1
        assert "Scope violation" in issues[0]
        assert "SingletonRoot" in issues[0]
