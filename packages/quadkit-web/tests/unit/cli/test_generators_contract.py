"""Generator contract test for the web CLI contributor."""

from __future__ import annotations

from pathlib import Path

from quadkit.testing.generators_contract import (
    assert_contributor_generators_render,
)
from quadkit.web.cli.contributor import WebCliContributor


def test_all_generators_render(tmp_path: Path) -> None:
    """Every declared generator renders into tmp_path."""
    count = assert_contributor_generators_render(WebCliContributor(), tmp_path=tmp_path)
    assert count >= 6
