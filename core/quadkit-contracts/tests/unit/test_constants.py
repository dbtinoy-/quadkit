from quadkit.contracts.core.constants import ALL_ENTRY_POINT_GROUPS, EP_PLUGINS


def test_ep_plugins_constant() -> None:
    assert EP_PLUGINS == "quadkit.plugins"


def test_ep_plugins_in_catalogue() -> None:
    assert EP_PLUGINS in ALL_ENTRY_POINT_GROUPS