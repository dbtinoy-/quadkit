"""Speculative execution module — draft-verify pattern and tool pre-fetching."""

from __future__ import annotations

from quadkit.ai.agents.speculation.draft_verify import DraftVerifyExecutor
from quadkit.ai.agents.speculation.predictor import KeywordToolCallPredictor
from quadkit.ai.agents.speculation.prefetcher import SpeculativeToolPreFetcher
from quadkit.ai.agents.speculation.protocols import ToolCallPredictorProtocol

__all__ = [
    "DraftVerifyExecutor",
    "KeywordToolCallPredictor",
    "SpeculativeToolPreFetcher",
    "ToolCallPredictorProtocol",
]
