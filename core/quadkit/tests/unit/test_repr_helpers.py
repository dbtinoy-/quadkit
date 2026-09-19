
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.module import Module
from quadkit.di.provider import Provider
from quadkit.di.resolution.descriptor import ServiceDescriptor


def test_service_descriptor_repr():
    desc = ServiceDescriptor(
        service_type=str,
        implementation=int,
        scope=ProviderPriority.NORMAL,  # misuse: just to include attr
    )
    r = repr(desc)
    assert "ServiceDescriptor" in r
    assert "service_type=str" in r


def test_module_repr():
    mod = Module(name="mymod", providers=[], imports=[], exports=[str])
    r = repr(mod)
    # Module instance repr delegates to class-level repr via ModuleMeta
    assert "Module" in r


def test_provider_repr():
    class MyProv(Provider):
        pass

    p = MyProv(name="x", priority=ProviderPriority.SECURITY, dependencies=("a",))
    r = repr(p)
    assert "MyProv" in r
    assert "name='x'" in r
    assert "priority=SECURITY" in r
