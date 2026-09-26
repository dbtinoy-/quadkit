"""Generator contract test for the storage CLI contributor."""

from __future__ import annotations

from pathlib import Path

from quadkit.storage.cli.contributor import StorageCliContributor
from quadkit.testing.generators_contract import (
    assert_contributor_generators_render,
)


def test_all_generators_render(tmp_path: Path) -> None:
    """Every declared generator renders into tmp_path."""
    count = assert_contributor_generators_render(
        StorageCliContributor(), tmp_path=tmp_path
    )
    assert count >= 1
