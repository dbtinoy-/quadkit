"""Generator contract test for the MCP CLI contributor (quadkit-ai-mcp).

Also gates the @INTENT/@TODO marker convention on the rendered controller and
server stubs — the shared harness scans every emitted ``.py`` for a bare
``# TODO`` and for any ``# @TODO`` missing its ``# @INTENT``.
"""

from __future__ import annotations

from pathlib import Path

from quadkit.ai.mcp.cli.contributor import McpCliContributor
from quadkit.testing.generators_contract import (
    assert_contributor_generators_render,
)


def test_all_generators_render(tmp_path: Path) -> None:
    """Every declared generator renders into tmp_path."""
    count = assert_contributor_generators_render(
        McpCliContributor(), tmp_path=tmp_path
    )
    assert count >= 2
