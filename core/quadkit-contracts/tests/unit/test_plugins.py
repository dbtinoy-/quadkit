from dataclasses import FrozenInstanceError

from quadkit.contracts.plugins import (
    PluginDescriptor,
    TaskPluginMarketplaceProtocol,
    TaskPluginMarketplaceSource,
)


def test_plugin_descriptor_is_frozen() -> None:
    d = PluginDescriptor(
        name="relay-gateway",
        display_name="AI Gateway",
        description="Adds AI relay/gateway capabilities.",
        icon="shuffle",
        provider_entry_point="relay-gateway",
    )
    assert d.name == "relay-gateway"
    assert d.provider_entry_point == "relay-gateway"
    try:
        d.name = "other"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("PluginDescriptor must be frozen")


def test_task_plugin_marketplace_source_is_frozen() -> None:
    source = TaskPluginMarketplaceSource(
        name="Official",
        index_url="https://plugins.example.test/index.json",
    )
    assert source.name == "Official"
    assert source.index_url.startswith("https://")
    try:
        source.name = "other"  # type: ignore[misc]
    except (AttributeError, FrozenInstanceError):
        pass
    else:
        raise AssertionError("TaskPluginMarketplaceSource must be frozen")


def test_task_plugin_marketplace_protocol_is_runtime_checkable() -> None:
    class Marketplace:
        async def get_sources(self) -> list[TaskPluginMarketplaceSource]:
            return []

        async def update_sources(
            self,
            sources: list[TaskPluginMarketplaceSource],
        ) -> list[TaskPluginMarketplaceSource]:
            return sources

    assert isinstance(Marketplace(), TaskPluginMarketplaceProtocol)
