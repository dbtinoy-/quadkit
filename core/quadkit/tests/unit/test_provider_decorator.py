import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.decorators import provider
from quadkit.di.provider import Provider


@provider(name="foo", priority=ProviderPriority.CRITICAL, dependencies=("bar",))
class FooProvider(Provider):
    pass


@provider()
class DefaultProvider(Provider):
    pass


class TestProviderDecorator:
    def test_metadata_applied(self):
        p = FooProvider()
        assert p.name == "foo"
        assert p.priority == ProviderPriority.CRITICAL
        assert p.dependencies == ("bar",)

    def test_defaults_preserved(self):
        p = DefaultProvider()
        # name is derived from class name
        assert p.name == "default"
        assert p.priority == ProviderPriority.NORMAL
        assert p.dependencies == ()

    def test_error_on_non_provider(self):
        with pytest.raises(TypeError):
            @provider(name="bad")
            class NotAProvider:
                pass
