"""Round 40 hardening pins — ai-agents: execution failures become Err.

AgentExecutorWithResultPattern.execute — any failure inside the
execution path (non-builtin driver error type) becomes
Err(AgentError), never a raw raise.

Run with: pytest tests/unit/test_round40_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quadkit.ai.agents.services import result_pattern_service as module
from quadkit.ai.agents.services.result_pattern_service import (
    AgentExecutorWithResultPattern,
)

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a driver error type (not RuntimeError/ValueError)."""


class TestAgentExecutorWithResultPattern:
    @pytest.mark.asyncio
    async def test_driver_error_becomes_err(self) -> None:
        service = AgentExecutorWithResultPattern()

        with patch.object(module, "logger") as mock_logger:
            mock_logger.info.side_effect = _DriverError("log sink wedged")

            result = await service.execute("agent-1", "do the thing")

        assert result.is_err()
