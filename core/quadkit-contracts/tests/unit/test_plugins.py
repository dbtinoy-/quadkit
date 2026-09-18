from quadkit.contracts.plugins import PluginDescriptor


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