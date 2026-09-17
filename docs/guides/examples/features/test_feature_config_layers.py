"""Feature tour: configuration — layered sources, one resolved model.

`BaseConfig` subclasses declare fields with defaults and let three
sources layer on top: explicit dicts, YAML files, and environment
variables. Two contracts are worth pinning. The precedence is
deterministic — environment variables win over file values, which win
over declared defaults — and a plain constructor reads declared defaults
only, so environment overlays always arrive through a loader path
(`from_yaml`, `from_dict`, or `ConfigProvider`). The application's own
config goes further: `Application.boot()` wires a `ConfigProvider`
automatically, and resolving `QuadkitConfig` from the container returns
the merged model with `QK_*` variables already applied.
"""

import pytest

from quadkit import Application, BaseConfig, QuadkitConfig


class ShopConfig(BaseConfig):
    tax_rate: float = 0.07
    shop_name: str = "quadkit bazaar"


def test_defaults_and_explicit_dicts() -> None:
    # Plain construction: exactly the declared defaults.
    bare = ShopConfig()
    assert bare.tax_rate == 0.07
    assert bare.shop_name == "quadkit bazaar"

    # from_dict: explicit literals land as given.
    given = ShopConfig.from_dict({"tax_rate": 0.10})
    assert given.tax_rate == 0.10


def test_env_overrides_file_and_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config_file = tmp_path / "shop.yaml"
    config_file.write_text("tax_rate: 0.15\nshop_name: yaml shop\n")

    # Without env: the file values win over declared defaults.
    from_file = ShopConfig.from_yaml(config_file)
    assert from_file.tax_rate == 0.15
    assert from_file.shop_name == "yaml shop"

    # With env (QK_ + field name, uppercased): env wins over the file.
    monkeypatch.setenv("QK_TAX_RATE", "0.25")
    merged = ShopConfig.from_yaml(config_file)
    assert merged.tax_rate == 0.25
    assert merged.shop_name == "yaml shop"


@pytest.mark.asyncio
async def test_quadkit_config_resolves_from_the_container(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    # Boot from an empty directory: with no application.yaml on the
    # search path the declared section defaults surface — the tour stays
    # portable to any working directory it is executed from.
    monkeypatch.chdir(tmp_path)
    # No providers passed: ConfigProvider is wired by boot itself.
    monkeypatch.setenv("QK_DEBUG", "true")
    async with Application.boot() as app:
        cfg = await app.container.resolve(QuadkitConfig)
        assert cfg.debug is True
        assert cfg.app_name == "quadkit-app"
