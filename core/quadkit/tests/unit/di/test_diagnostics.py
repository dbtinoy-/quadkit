from unittest.mock import MagicMock, patch

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.resolution.diagnostics import ContainerDiagnostics
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.type_hints import TypeHintResolverImpl


def test_dump_registrations():
    registry = MagicMock(spec=ServiceRegistry)
    descriptor = MagicMock()
    descriptor.service_type = str  # Example type
    descriptor.implementation = None
    descriptor.scope = ServiceScope.SINGLETON
    descriptor.instance = "hello"
    
    registry.all.return_value = [descriptor]
    
    diagnostics = ContainerDiagnostics(registry, MagicMock())
    dump = diagnostics.dump_registrations()
    
    assert len(dump) == 1
    assert dump[0]["service"] == "str"
    assert dump[0]["scope"] == "singleton"
    assert dump[0]["has_instance"] is True


def test_dump_registrations_no_implementation():
    """Test dump_registrations when implementation is None."""
    registry = MagicMock(spec=ServiceRegistry)
    descriptor = MagicMock()
    descriptor.service_type = str
    descriptor.implementation = None
    descriptor.scope = ServiceScope.TRANSIENT
    descriptor.instance = None
    
    registry.all.return_value = [descriptor]
    
    diagnostics = ContainerDiagnostics(registry, MagicMock())
    dump = diagnostics.dump_registrations()
    
    assert len(dump) == 1
    assert dump[0]["implementation"] is None


def test_dump_dependency_graph():
    registry = MagicMock(spec=ServiceRegistry)
    type_resolver = MagicMock(spec=TypeHintResolverImpl)
    
    class Svc:
        pass

    class Dep:
        pass
    
    descriptor = MagicMock()
    descriptor.service_type = Svc
    descriptor.implementation = Svc
    
    registry.all.return_value = [descriptor]
    registry.has.side_effect = lambda t: t == Dep
    type_resolver.get_type_dependencies.return_value = [Dep]
    
    diagnostics = ContainerDiagnostics(registry, type_resolver)
    graph = diagnostics.dump_dependency_graph()
    
    assert "Svc" in graph
    assert graph["Svc"] == ["Dep"]


def test_dump_dependency_graph_non_class():
    """Test dump_dependency_graph when implementation is not a class."""
    registry = MagicMock(spec=ServiceRegistry)
    type_resolver = MagicMock(spec=TypeHintResolverImpl)
    
    descriptor = MagicMock()
    descriptor.service_type = "string"
    descriptor.implementation = "factory"
    
    registry.all.return_value = [descriptor]
    
    diagnostics = ContainerDiagnostics(registry, type_resolver)
    graph = diagnostics.dump_dependency_graph()
    
    assert "string" in graph
    assert graph["string"] == []


def test_dump_dependency_graph_exception():
    """Test dump_dependency_graph handles exceptions from resolver."""
    registry = MagicMock(spec=ServiceRegistry)
    type_resolver = MagicMock(spec=TypeHintResolverImpl)
    
    class Svc:
        pass
    
    descriptor = MagicMock()
    descriptor.service_type = Svc
    descriptor.implementation = Svc
    
    registry.all.return_value = [descriptor]
    type_resolver.get_type_dependencies.side_effect = TypeError("test error")
    
    diagnostics = ContainerDiagnostics(registry, type_resolver)
    graph = diagnostics.dump_dependency_graph()
    
    assert "Svc" in graph
    assert graph["Svc"] == []


def test_log_registrations_empty(caplog):
    """Test log_registrations with no registrations."""
    import logging
    
    registry = MagicMock(spec=ServiceRegistry)
    registry.all.return_value = []
    
    diagnostics = ContainerDiagnostics(registry, MagicMock())
    diagnostics.log_registrations()


def test_log_registrations_with_entries(caplog):
    """Test log_registrations with registrations."""
    import logging
    
    registry = MagicMock(spec=ServiceRegistry)
    descriptor = MagicMock()
    descriptor.service_type = str
    descriptor.implementation = None
    descriptor.scope = ServiceScope.SINGLETON
    descriptor.instance = None
    
    registry.all.return_value = [descriptor]
    
    diagnostics = ContainerDiagnostics(registry, MagicMock())
    diagnostics.log_registrations()
