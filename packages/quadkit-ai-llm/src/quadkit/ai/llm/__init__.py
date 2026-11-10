"""LLM module exports."""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.ai.llm.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.ai.llm.caching.core import (
        CacheEntry,
        CacheStats,
        LLMCache,
        RedisLLMCache,
    )
    from quadkit.ai.llm.clients.anthropic import AnthropicClient
    from quadkit.ai.llm.clients.cohere import CohereClient
    from quadkit.ai.llm.clients.groq import GroqClient
    from quadkit.ai.llm.clients.mistral import MistralClient
    from quadkit.ai.llm.clients.ollama import OllamaClient
    from quadkit.ai.llm.clients.openai import OpenAIClient
    from quadkit.ai.llm.clients.openrouter import OpenRouterClient
    from quadkit.ai.llm.config import ClientConfig
    from quadkit.ai.llm.conversation.manager import (
        ConversationConfig,
        ConversationManager,
        ConversationStats,
    )
    from quadkit.ai.llm.events import LLMCompletionEvent
    from quadkit.ai.llm.extraction.extractor import InstructorExtractor
    from quadkit.ai.llm.hooks import (
        LLMProviderRegisteredHook,
        LLMRequestSentHook,
        LLMResponseReceivedHook,
    )
    from quadkit.ai.llm.metrics.collector import (
        CacheMetrics,
        ErrorMetrics,
        MetricsCollector,
        MetricsSnapshot,
        MetricType,
        TimingMetrics,
        UsageMetrics,
    )
from quadkit.ai.llm.pricing import (
    AbstractPricingSource,
    JSONFilePricingSource,
    StaticPricingSource,
)
from quadkit.ai.llm.pricing.registry import TokenCounterRegistry
from quadkit.ai.llm.protocols import LLMCacheProtocol
from quadkit.ai.llm.rate_limiting.core import RateLimiter
from quadkit.ai.llm.registry.core import ProviderInfo, ProviderRegistry
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    LogConfig,
    ProviderConfig,
    QuotaConfig,
)
from quadkit.ai.llm.security.core import (
    OutputFilter,
    SecureLLMClient,
    SecurePromptTemplate,
    create_assistant_template,
    create_data_extraction_template,
)
from quadkit.ai.llm.selection.core import (
    ModelCapabilities,
    ModelSelector,
    SelectionCriteria,
    SelectionStrategy,
    create_balanced_selector,
    create_cost_optimized_selector,
    create_quality_optimized_selector,
)
from quadkit.ai.llm.structured.exceptions import (
    ParseError,
    SchemaValidationError,
    StructuredOutputError,
)
from quadkit.ai.llm.structured.extractor import JSONExtractor
from quadkit.ai.llm.structured.formatter import ResponseFormatter
from quadkit.ai.llm.structured.parser import StructuredOutputParser
from quadkit.ai.llm.structured.utils import (
    complete_with_json,
    complete_with_schema,
    create_json_mode_messages,
)
from quadkit.ai.llm.types import (
    ChatMessage,
    Completion,
    FunctionCall,
    LLMError,
    Role,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from quadkit.contracts.ai.multimodal import (
    ContentPart,
    ImageBase64Part,
    ImageUrlPart,
    MessageContent,
    TextPart,
)

_LAZY_IMPORTS: dict[str, str] = {
    "normalize_thinking_text": "quadkit.ai.llm.thinking",
    # Events
    "LLMCompletionEvent": "quadkit.ai.llm.events",
    # Hooks
    "LLMProviderRegisteredHook": "quadkit.ai.llm.hooks",
    "LLMRequestSentHook": "quadkit.ai.llm.hooks",
    "LLMResponseReceivedHook": "quadkit.ai.llm.hooks",
    # Metrics
    "CacheMetrics": "quadkit.ai.llm.metrics.collector",
    "ErrorMetrics": "quadkit.ai.llm.metrics.collector",
    "MetricType": "quadkit.ai.llm.metrics.collector",
    "MetricsCollector": "quadkit.ai.llm.metrics.collector",
    "MetricsSnapshot": "quadkit.ai.llm.metrics.collector",
    "TimingMetrics": "quadkit.ai.llm.metrics.collector",
    "UsageMetrics": "quadkit.ai.llm.metrics.collector",
    # Types
    "AnthropicClient": "quadkit.ai.llm.clients.anthropic",
    "APIPricingSource": "quadkit.ai.llm.pricing",
    "CacheEntry": "quadkit.ai.llm.caching.core",
    "CacheStats": "quadkit.ai.llm.caching.core",
    "ChatMessage": "quadkit.ai.llm.types",
    "ContentPart": "quadkit.contracts.ai.multimodal",
    # Config
    "ClientConfig": "quadkit.ai.llm.config",
    "CohereClient": "quadkit.ai.llm.clients.cohere",
    "Completion": "quadkit.ai.llm.types",
    "ConversationConfig": "quadkit.ai.llm.conversation.manager",
    "ConversationManager": "quadkit.ai.llm.conversation.manager",
    "ConversationStats": "quadkit.ai.llm.conversation.manager",
    "CostEstimate": "quadkit.ai.llm.pricing.tokens",
    "FunctionCall": "quadkit.ai.llm.types",
    "GenerationDefaults": "quadkit.ai.llm.routing.config",
    "GroqClient": "quadkit.ai.llm.clients.groq",
    "ImageBase64Part": "quadkit.contracts.ai.multimodal",
    "ImageUrlPart": "quadkit.contracts.ai.multimodal",
    "InstructorExtractor": "quadkit.ai.llm.extraction.extractor",
    "JSONExtractor": "quadkit.ai.llm.structured.extractor",
    "JSONFilePricingSource": "quadkit.ai.llm.pricing",
    "LLMCache": "quadkit.ai.llm.caching.core",
    "LLMCacheProtocol": "quadkit.ai.llm.protocols",
    "LLMConfig": "quadkit.ai.llm.routing.config",
    "LogConfig": "quadkit.ai.llm.routing.config",
    "LLMError": "quadkit.ai.llm.types",
    "LLMAuthenticationError": "quadkit.ai.llm.exceptions",
    "LLMContentFilterError": "quadkit.ai.llm.exceptions",
    "LLMModelNotFoundError": "quadkit.ai.llm.exceptions",
    "ModelRevisionMismatchError": "quadkit.ai.llm.exceptions",
    "LLMQuotaExceededError": "quadkit.ai.llm.exceptions",
    "LLMRateLimitError": "quadkit.ai.llm.exceptions",
    "InvalidRequestError": "quadkit.ai.llm.exceptions",
    "ModelNotFoundError": "quadkit.ai.llm.exceptions",
    "ProviderConnectionError": "quadkit.ai.llm.exceptions",
    "StreamError": "quadkit.ai.llm.exceptions",
    "TokenLimitError": "quadkit.ai.llm.exceptions",
    "ExtractionError": "quadkit.ai.llm.exceptions",
    "ExtractionParseError": "quadkit.ai.llm.exceptions",
    "ExtractionValidationError": "quadkit.ai.llm.exceptions",
    "ExtractionMaxRetriesError": "quadkit.ai.llm.exceptions",
    "MessageContent": "quadkit.contracts.ai.multimodal",
    "MistralClient": "quadkit.ai.llm.clients.mistral",
    "ModelCapabilities": "quadkit.ai.llm.selection.core",
    "ModelPricing": "quadkit.ai.llm.pricing",
    "ModelSelector": "quadkit.ai.llm.selection.core",
    "OllamaClient": "quadkit.ai.llm.clients.ollama",
    "OpenAIClient": "quadkit.ai.llm.clients.openai",
    "OpenRouterClient": "quadkit.ai.llm.clients.openrouter",
    "OpenRouterPricingSource": "quadkit.ai.llm.pricing",
    "OutputFilter": "quadkit.ai.llm.security.core",
    "ParseError": "quadkit.ai.llm.structured.exceptions",
    "PricingConfig": "quadkit.ai.llm.config",
    "PricingCostEstimator": "quadkit.ai.llm.pricing.estimator",
    "PricingManager": "quadkit.ai.llm.pricing",
    "PricingManagerBuilder": "quadkit.ai.llm.pricing",
    "PricingSourceConfig": "quadkit.ai.llm.config",
    "AbstractPricingSource": "quadkit.ai.llm.pricing",
    "ProviderConfig": "quadkit.ai.llm.routing.config",
    # Pinning
    "ModelPinPolicy": "quadkit.ai.llm.pinning",
    "enforce_pin_policy": "quadkit.ai.llm.pinning",
    # Audit
    "LLMAuditBridge": "quadkit.ai.llm.audit_bridge",
    # Parsers
    "ParserRegistry": "quadkit.ai.llm.parsers.registry",
    "JSONOutputParser": "quadkit.ai.llm.parsers.json",
    "PydanticOutputParser": "quadkit.ai.llm.parsers.pydantic",
    "EnumOutputParser": "quadkit.ai.llm.parsers.enum",
    "CSVOutputParser": "quadkit.ai.llm.parsers.csv",
    "FormatFixingParser": "quadkit.ai.llm.parsers.fixing",
    "ProviderInfo": "quadkit.ai.llm.registry.core",
    "ProviderRegistry": "quadkit.ai.llm.registry.core",
    "QuotaConfig": "quadkit.ai.llm.routing.config",
    "RateLimiter": "quadkit.ai.llm.rate_limiting.core",
    "RedisLLMCache": "quadkit.ai.llm.caching.core",
    "ResponseFormatter": "quadkit.ai.llm.structured.formatter",
    "Role": "quadkit.ai.llm.types",
    "SchemaValidationError": "quadkit.ai.llm.structured.exceptions",
    "SecureLLMClient": "quadkit.ai.llm.security.core",
    "SecurePromptTemplate": "quadkit.ai.llm.security.core",
    "SelectionCriteria": "quadkit.ai.llm.selection.core",
    "SelectionStrategy": "quadkit.ai.llm.selection.core",
    "StaticPricingSource": "quadkit.ai.llm.pricing",
    "StreamChunk": "quadkit.ai.llm.types",
    "StructuredOutputError": "quadkit.ai.llm.structured.exceptions",
    "StructuredOutputParser": "quadkit.ai.llm.structured.parser",
    "TextPart": "quadkit.contracts.ai.multimodal",
    "TokenCount": "quadkit.ai.llm.pricing.tokens",
    "TiktokenCounter": "quadkit.ai.llm.pricing.tokens",
    "CharEstimateCounter": "quadkit.ai.llm.pricing.tokens",
    "HuggingFaceCounter": "quadkit.ai.llm.pricing.tokens",
    "MistralCounter": "quadkit.ai.llm.pricing.tokens",
    "TokenCounterRegistry": "quadkit.ai.llm.pricing.registry",
    "TokenUsage": "quadkit.ai.llm.types",
    "ToolCall": "quadkit.ai.llm.types",
    "complete_with_json": "quadkit.ai.llm.structured.utils",
    "complete_with_schema": "quadkit.ai.llm.structured.utils",
    "create_assistant_template": "quadkit.ai.llm.security.core",
    "create_balanced_selector": "quadkit.ai.llm.selection.core",
    "create_cost_optimized_selector": "quadkit.ai.llm.selection.core",
    "create_data_extraction_template": "quadkit.ai.llm.security.core",
    "create_json_mode_messages": "quadkit.ai.llm.structured.utils",
    "create_quality_optimized_selector": "quadkit.ai.llm.selection.core",
    "create_token_counter": "quadkit.ai.llm.pricing.tokens",
    # DI
    "LLMModule": "quadkit.ai.llm.module",
    "LLMProvider": "quadkit.ai.llm.di.provider",
    "LLMRoutingProvider": "quadkit.ai.llm.di.routing_provider",
    # Runnable composition
    "RunnableBranch": "quadkit.ai.llm.runnable",
    "RunnableLambda": "quadkit.ai.llm.runnable",
    "RunnableMixin": "quadkit.ai.llm.runnable",
    "RunnableParallel": "quadkit.ai.llm.runnable",
    "RunnablePassthrough": "quadkit.ai.llm.runnable",
    "RunnableSequence": "quadkit.ai.llm.runnable",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib as _importlib

        module = _importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS.keys())
