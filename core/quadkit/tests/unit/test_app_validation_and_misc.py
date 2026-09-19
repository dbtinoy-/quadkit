"""Tests for boot-time config validation, InjectableAutoProvider, and the
re-export expansion compiler phase."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.app.config_validation import validate_app_config
from quadkit.app.injectable_provider import InjectableAutoProvider
from quadkit.contracts.core.scopes import ServiceScope
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.compiler.phases.expand import ReexportExpansionPhase
from quadkit.di.module.graph import ModuleNode
from quadkit.di.module.metadata import ModuleMetadata

# ---------------------------------------------------------------------------
# validate_app_config
# ---------------------------------------------------------------------------


def _issue(severity: str, field: str = "f", message: str = "msg", suggestion: str | None = None):
    i = MagicMock()
    i.severity = severity
    i.field = field
    i.message = message
    i.suggestion = suggestion
    return i


class TestValidateAppConfig:
    def test_no_issues_no_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # validate_all_configs is imported locally inside the function.
        import quadkit.config.lib.validation as vlib

        def _no_issues(configs: list) -> list:
            del configs
            return []

        monkeypatch.setattr(vlib, "validate_all_configs", _no_issues)
        logger = MagicMock()
        validate_app_config(MagicMock(), logger)
        logger.warning.assert_not_called()

    def test_warnings_logged_not_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import quadkit.config.lib.validation as vlib

        def _warn_issues(configs: list) -> list:
            del configs
            return [_issue("warning", "debug", "w1", "s1")]

        monkeypatch.setattr(vlib, "validate_all_configs", _warn_issues)
        logger = MagicMock()
        validate_app_config(MagicMock(), logger)
        logger.warning.assert_called_once()
        assert logger.warning.call_args.kwargs["field"] == "debug"

    def test_error_issues_abort_with_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import quadkit.config.lib.validation as vlib

        issues = [
            _issue("error", "debug", "debug in prod", "set debug=false"),
            _issue("warning", "env", "warn"),
        ]
        def _error_issues(configs: list) -> list:
            del configs
            return issues

        monkeypatch.setattr(vlib, "validate_all_configs", _error_issues)
        logger = MagicMock()
        with pytest.raises(ConfigurationError, match="refusing to start"):
            validate_app_config(MagicMock(), logger)
        # Warning was still logged before abort.
        logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# InjectableAutoProvider
# ---------------------------------------------------------------------------


class _SvcS:
    pass


class _SvcC:
    pass


class _SvcT:
    pass


class _RecordingRegistrar:
    def __init__(self) -> None:
        self.calls: dict[str, list[type]] = {"singleton": [], "scoped": [], "transient": []}

    def singleton(self, cls: type, factory: Any = None) -> None:
        self.calls["singleton"].append(cls)

    def scoped(self, cls: type, factory: Any = None) -> None:
        self.calls["scoped"].append(cls)

    def transient(self, cls: type, factory: Any = None) -> None:
        self.calls["transient"].append(cls)


class TestInjectableAutoProvider:
    async def test_registers_each_scope(self) -> None:
        provider = InjectableAutoProvider(
            [
                (_SvcS, ServiceScope.SINGLETON),
                (_SvcC, ServiceScope.SCOPED),
                (_SvcT, ServiceScope.TRANSIENT),
            ]
        )
        assert provider.name == "_injectable_auto"
        reg = _RecordingRegistrar()
        await provider.register(reg)  # type: ignore[arg-type]
        assert reg.calls["singleton"] == [_SvcS]
        assert reg.calls["scoped"] == [_SvcC]
        assert reg.calls["transient"] == [_SvcT]

    async def test_empty_list_is_noop(self) -> None:
        provider = InjectableAutoProvider([])
        reg = _RecordingRegistrar()
        await provider.register(reg)  # type: ignore[arg-type]
        assert reg.calls == {"singleton": [], "scoped": [], "transient": []}


# ---------------------------------------------------------------------------
# ReexportExpansionPhase
# ---------------------------------------------------------------------------


def _node(cls: type, name: str, imports: list[type] | None = None, exports: frozenset[type] | None = None) -> ModuleNode:
    return ModuleNode(
        module_class=cls,
        name=name,
        metadata=ModuleMetadata(name=name),
        providers=[],
        imports=imports or [],
        exports=exports or frozenset(),
        is_global=False,
        is_dynamic=False,
        controllers=[],
        health_providers=None,  # type: ignore[arg-type]
    )


def _make_module(n: int) -> type:
    return type(f"Mod{n}", (), {})


class TestReexportExpansion:
    def test_module_class_export_expands_to_concrete(self) -> None:
        base, api = _make_module(1), _make_module(2)

        class Concrete:
            pass

        ctx = CompilerContext(root_modules=[api], standalone_providers=[], nodes={
            base: _node(base, "base", exports=frozenset({Concrete})),
            api: _node(api, "api", imports=[base], exports=frozenset({base})),
        }, dynamic_configs={}, visibility={}, global_exports=set(), provider_order=[], warnings=[])
        ReexportExpansionPhase().execute(ctx)
        assert ctx.nodes[api].exports == frozenset({Concrete})
        # Base node untouched.
        assert ctx.nodes[base].exports == frozenset({Concrete})

    def test_transitive_reexport_expands(self) -> None:
        base, mid, top = _make_module(1), _make_module(2), _make_module(3)

        class Concrete:
            pass

        ctx = CompilerContext(root_modules=[top], standalone_providers=[], nodes={
            base: _node(base, "base", exports=frozenset({Concrete})),
            mid: _node(mid, "mid", imports=[base], exports=frozenset({base})),
            top: _node(top, "top", imports=[mid], exports=frozenset({mid})),
        }, dynamic_configs={}, visibility={}, global_exports=set(), provider_order=[], warnings=[])
        ReexportExpansionPhase().execute(ctx)
        assert ctx.nodes[mid].exports == frozenset({Concrete})
        assert ctx.nodes[top].exports == frozenset({Concrete})

    def test_concrete_exports_unchanged(self) -> None:
        solo = _make_module(1)

        class Proto:
            pass

        ctx = CompilerContext(root_modules=[solo], standalone_providers=[], nodes={
            solo: _node(solo, "solo", exports=frozenset({Proto})),
        }, dynamic_configs={}, visibility={}, global_exports=set(), provider_order=[], warnings=[])
        ReexportExpansionPhase().execute(ctx)
        assert ctx.nodes[solo].exports == frozenset({Proto})

    def test_mixed_module_and_concrete_exports(self) -> None:
        base, api = _make_module(1), _make_module(2)

        class Own:
            pass

        class FromBase:
            pass

        ctx = CompilerContext(root_modules=[api], standalone_providers=[], nodes={
            base: _node(base, "base", exports=frozenset({FromBase})),
            api: _node(api, "api", imports=[base], exports=frozenset({Own, base})),
        }, dynamic_configs={}, visibility={}, global_exports=set(), provider_order=[], warnings=[])
        ReexportExpansionPhase().execute(ctx)
        assert ctx.nodes[api].exports == frozenset({Own, FromBase})

    def test_node_identity_replaced_on_change(self) -> None:
        base, api = _make_module(1), _make_module(2)

        class Concrete:
            pass

        api_node_before = _node(api, "api", imports=[base], exports=frozenset({base}))
        ctx = CompilerContext(root_modules=[api], standalone_providers=[], nodes={
            base: _node(base, "base", exports=frozenset({Concrete})),
            api: api_node_before,
        }, dynamic_configs={}, visibility={}, global_exports=set(), provider_order=[], warnings=[])
        ReexportExpansionPhase().execute(ctx)
        assert ctx.nodes[api] is not api_node_before
        assert ctx.nodes[api].exports == frozenset({Concrete})
