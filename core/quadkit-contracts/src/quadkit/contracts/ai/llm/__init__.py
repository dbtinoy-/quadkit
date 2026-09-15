"""LLM client and prompt protocols."""

from __future__ import annotations

from quadkit.contracts.ai.exceptions import ExtractionError as ExtractionError
from quadkit.contracts.ai.exceptions import LLMError as LLMError
from quadkit.contracts.ai.llm.protocols import (
    ChatMessageProtocol as ChatMessageProtocol,
)
from quadkit.contracts.ai.llm.protocols import CompletionProtocol as CompletionProtocol
from quadkit.contracts.ai.llm.protocols import (
    CostEstimatorProtocol as CostEstimatorProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    EmbeddingClientProtocol as EmbeddingClientProtocol,
)
from quadkit.contracts.ai.llm.protocols import LLMClientProtocol as LLMClientProtocol
from quadkit.contracts.ai.llm.protocols import (
    PromptAssemblerProtocol as PromptAssemblerProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    PromptOptimizerProtocol as PromptOptimizerProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    PromptRegistryProtocol as PromptRegistryProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    PromptRendererProtocol as PromptRendererProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    PromptTemplateProtocol as PromptTemplateProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    SemanticCacheProtocol as SemanticCacheProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    StructuredExtractorProtocol as StructuredExtractorProtocol,
)
from quadkit.contracts.ai.llm.protocols import (
    TokenCounterProtocol as TokenCounterProtocol,
)
from quadkit.contracts.ai.llm.types import ChatMessage as ChatMessage
from quadkit.contracts.ai.llm.types import Completion as Completion
from quadkit.contracts.ai.llm.types import FunctionCall as FunctionCall
from quadkit.contracts.ai.llm.types import Role as Role
from quadkit.contracts.ai.llm.types import StreamChunk as StreamChunk
from quadkit.contracts.ai.llm.types import StreamEvent as StreamEvent
from quadkit.contracts.ai.llm.types import TokenBudget as TokenBudget
from quadkit.contracts.ai.llm.types import TokenUsage as TokenUsage
from quadkit.contracts.ai.llm.types import ToolCall as ToolCall
from quadkit.contracts.ai.thinking import ThinkingConfig as ThinkingConfig
from quadkit.contracts.ai.thinking import ThinkingResult as ThinkingResult
from quadkit.contracts.infra import AsyncStream as AsyncStream

__all__ = [
    "AsyncStream",
    "ChatMessage",
    "ChatMessageProtocol",
    "Completion",
    "CompletionProtocol",
    "CostEstimatorProtocol",
    "EmbeddingClientProtocol",
    "ExtractionError",
    "FunctionCall",
    "LLMClientProtocol",
    "LLMError",
    "PromptAssemblerProtocol",
    "PromptOptimizerProtocol",
    "PromptRegistryProtocol",
    "PromptRendererProtocol",
    "PromptTemplateProtocol",
    "Role",
    "SemanticCacheProtocol",
    "StreamChunk",
    "StreamEvent",
    "StructuredExtractorProtocol",
    "ThinkingConfig",
    "ThinkingResult",
    "TokenBudget",
    "TokenCounterProtocol",
    "TokenUsage",
    "ToolCall",
]
