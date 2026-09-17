"""Feature tour: config sources — layered, typed, and typo-proof.

Applications rarely want a single config origin: a committed base file,
an environment-specific overlay, and process env vars on top.
``ConfigProvider`` takes ``sources=[...]`` — each source contributes a
mapping, and later sources deep-merge over earlier ones per key, so
base values fall through where the overlay stays silent. Environment
variables (``QK_`` prefix, ``__`` for nesting) always land on top,
matching the loader convention everywhere else in the framework. And
custom sections stay *typed*: ``extensions={"shop": ShopConfig}``
teaches the root config your model, and the strict unknown-key policy
still guards it — a typo in ``application.yaml`` is a named error at
boot, not silent drift.
"""

import pathlib

import pytest

from quadkit import Application, BaseConfig, ConfigProvider, QuadkitConfig
from quadkit.config import EnvironmentConfigSource, FileConfigSource
from quadkit.config.exceptions import ConfigSourceError


class ShopConfig(BaseConfig):
    tax_rate: float = 0.07
    prefix: str = "dead"
    flavor: str = "plain"


@pytest.fixture
def layered(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    base = tmp_path / "base.yaml"
    base.write_text("shop:\n  tax_rate: 0.10\n  prefix: base\n  flavor: from-base\n")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text("shop:\n  tax_rate: 0.20\n  prefix: overlay\n")
    return base, overlay


async def resolve_shop(
    sources: list,  # noqa: ANN401 — heterogeneous ConfigSource list
) -> ShopConfig:
    async with Application.boot(
        providers=[ConfigProvider(extensions={"shop": ShopConfig}, sources=sources)]
    ) as app:
        root = await app.container.resolve(QuadkitConfig)
        return root.get_section("shop", ShopConfig)


@pytest.mark.asyncio
async def test_later_sources_override_per_key(
    layered: tuple[pathlib.Path, pathlib.Path],
) -> None:
    base, overlay = layered
    shop = await resolve_shop([FileConfigSource(base), FileConfigSource(overlay)])

    # Overlay keys win…
    assert shop.tax_rate == 0.20
    assert shop.prefix == "overlay"
    # …and keys absent from the overlay fall through to the base layer.
    assert shop.flavor == "from-base"


@pytest.mark.asyncio
async def test_environment_lands_on_top_of_every_file(
    layered: tuple[pathlib.Path, pathlib.Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, overlay = layered
    # QK_ + double-underscore nesting addresses the extension section.
    monkeypatch.setenv("QK_SHOP__TAX_RATE", "0.33")
    shop = await resolve_shop(
        [FileConfigSource(overlay), EnvironmentConfigSource(prefix="QK_")]
    )
    assert shop.tax_rate == 0.33
    # The file layer still supplies what env did not name.
    assert shop.prefix == "overlay"


@pytest.mark.asyncio
async def test_typos_fail_fast_with_named_keys(tmp_path: pathlib.Path) -> None:
    typo = tmp_path / "typo.yaml"
    typo.write_text("shop:\n  tax_rte: 0.12\n")
    with pytest.raises(ConfigSourceError, match=r"Unknown configuration key.*'shop'"):
        await resolve_shop([FileConfigSource(typo)])
