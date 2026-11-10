"""Built-in LLM provider catalogue for the provider registry.

This module holds the single declaration of the built-in provider set
consumed by :class:`~quadkit.ai.llm.registry.core.ProviderRegistry`.
Each client module is imported lazily inside
:func:`builtin_provider_entries`, which runs at ``with_defaults()``
construction time, keeping all SDK imports deferred away from module
top-levels while still populating the registry catalogue.
"""

from __future__ import annotations

from typing import Any

__all__ = ["builtin_provider_entries"]


def builtin_provider_entries() -> tuple[dict[str, Any], ...]:
    """Declare the complete in-package built-in provider set.

    Returns one kwargs dict per provider, shaped exactly like
    ``ProviderRegistry.register()`` arguments.  Client classes are
    imported lazily inside this function so SDK imports stay deferred
    until a registry is actually populated with defaults.
    """
    entries: list[dict[str, Any]] = []

    # OpenAI
    from quadkit.ai.llm.clients.openai import OpenAIClient

    entries.append(
        {
            "name": "openai",
            "client_class": OpenAIClient,
            "default_models": [
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-3.5-turbo",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "base_url": "https://api.openai.com/v1",
            "docs_url": "https://platform.openai.com/docs",
            "pricing_url": "https://openai.com/pricing",
            "description": "OpenAI GPT models - industry standard for general purpose AI",
        }
    )

    # Anthropic (Claude)
    from quadkit.ai.llm.clients.anthropic import AnthropicClient

    entries.append(
        {
            "name": "anthropic",
            "client_class": AnthropicClient,
            "default_models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "base_url": "https://api.anthropic.com",
            "docs_url": "https://docs.anthropic.com",
            "pricing_url": "https://www.anthropic.com/pricing",
            "description": "Anthropic Claude - strong reasoning and long context (200k tokens)",
        }
    )

    # Groq
    from quadkit.ai.llm.clients.groq import GroqClient

    entries.append(
        {
            "name": "groq",
            "client_class": GroqClient,
            "default_models": [
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.groq.com/openai/v1",
            "docs_url": "https://console.groq.com/docs",
            "pricing_url": "https://groq.com/pricing",
            "description": "Groq - ultra-fast inference with LPU hardware (100+ tokens/sec, currently free)",
        }
    )

    # Mistral
    from quadkit.ai.llm.clients.mistral import MistralClient

    entries.append(
        {
            "name": "mistral",
            "client_class": MistralClient,
            "default_models": [
                "mistral-large-latest",
                "mistral-medium-latest",
                "mistral-small-latest",
                "open-mixtral-8x7b",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.mistral.ai/v1",
            "docs_url": "https://docs.mistral.ai",
            "pricing_url": "https://mistral.ai/technology/#pricing",
            "description": "Mistral AI - GDPR-compliant EU provider with strong multilingual support",
        }
    )

    # Cohere
    from quadkit.ai.llm.clients.cohere import CohereClient

    entries.append(
        {
            "name": "cohere",
            "client_class": CohereClient,
            "default_models": [
                "command-r-plus",
                "command-r",
                "command",
                "embed-english-v3.0",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.cohere.ai/v1",
            "docs_url": "https://docs.cohere.com",
            "pricing_url": "https://cohere.com/pricing",
            "description": "Cohere - best-in-class embeddings, reranking, and RAG-optimized models",
        }
    )

    # Ollama
    from quadkit.ai.llm.clients.ollama import OllamaClient

    entries.append(
        {
            "name": "ollama",
            "client_class": OllamaClient,
            "default_models": [
                "llama3:8b",
                "llama3:70b",
                "mistral:7b",
                "codellama:13b",
            ],
            "supports_streaming": True,
            "supports_tools": False,
            "supports_vision": False,
            "base_url": "http://localhost:11434",
            "docs_url": "https://ollama.ai/docs",
            "pricing_url": None,
            "description": "Ollama - run LLMs locally with zero API costs and full privacy",
        }
    )

    # OpenRouter
    from quadkit.ai.llm.clients.openrouter import OpenRouterClient

    entries.append(
        {
            "name": "openrouter",
            "client_class": OpenRouterClient,
            "default_models": ["gpt-4o", "gpt-4o-mini"],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.openrouter.ai/v1",
            "docs_url": "https://docs.openrouter.ai",
            "pricing_url": None,
            "description": "OpenRouter - open and compatible routing layer for many models",
        }
    )

    # Gemini
    from quadkit.ai.llm.clients.gemini import GeminiClient

    entries.append(
        {
            "name": "gemini",
            "client_class": GeminiClient,
            "default_models": [
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
            ],
            "supports_streaming": False,
            "supports_tools": False,
            "supports_vision": True,
            "base_url": "https://generativelanguage.googleapis.com",
            "docs_url": "https://ai.google.dev/docs",
            "pricing_url": "https://ai.google.dev/pricing",
            "description": "Google Gemini — multimodal models with vision and long context; free tier available",
        }
    )

    # Cloudflare Workers AI
    from quadkit.ai.llm.clients.cloudflare_workers import CloudflareWorkersClient

    entries.append(
        {
            "name": "cloudflare",
            "client_class": CloudflareWorkersClient,
            "default_models": [
                "@cf/meta/llama-3.2-11b-vision-instruct",
                "@cf/meta/llama-3.1-8b-instruct",
                "@cf/mistral/mistral-7b-instruct-v0.2",
            ],
            "supports_streaming": False,
            "supports_tools": False,
            "supports_vision": True,
            "base_url": "https://api.cloudflare.com",
            "docs_url": "https://developers.cloudflare.com/workers-ai",
            "pricing_url": "https://developers.cloudflare.com/workers-ai/platform/pricing/",
            "description": "Cloudflare Workers AI — serverless inference with vision models; free tier available",
        }
    )

    # Azure OpenAI
    from quadkit.ai.llm.clients.azure_openai import AzureOpenAIClient

    entries.append(
        {
            "name": "azure-openai",
            "client_class": AzureOpenAIClient,
            "default_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "base_url": "https://{resource}.openai.azure.com/openai",
            "docs_url": "https://learn.microsoft.com/azure/ai-services/openai/",
            "pricing_url": "https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/",
            "description": "Azure OpenAI — enterprise OpenAI deployment with Azure identity and networking controls",
        }
    )

    # AWS Bedrock
    from quadkit.ai.llm.clients.aws_bedrock import BedrockClient

    entries.append(
        {
            "name": "aws-bedrock",
            "client_class": BedrockClient,
            "default_models": [
                "anthropic.claude-3-5-sonnet-20240620-v1:0",
                "meta.llama3-70b-instruct-v1:0",
                "amazon.titan-text-express-v1",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "base_url": "https://bedrock-runtime.{region}.amazonaws.com",
            "docs_url": "https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html",
            "pricing_url": "https://aws.amazon.com/bedrock/pricing/",
            "description": "AWS Bedrock — managed foundation model platform with native AWS IAM and enterprise controls",
        }
    )

    # Google Vertex AI
    from quadkit.ai.llm.clients.vertex_ai import VertexAIClient

    entries.append(
        {
            "name": "google-vertex",
            "client_class": VertexAIClient,
            "default_models": [
                "gemini-2.0-flash",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": True,
            "base_url": "https://{region}-aiplatform.googleapis.com",
            "docs_url": "https://cloud.google.com/vertex-ai/docs/generative-ai/",
            "pricing_url": "https://cloud.google.com/vertex-ai/pricing",
            "description": "Google Vertex AI — enterprise Gemini deployment with GCP IAM and regional controls",
        }
    )

    # OpenAI-compatible providers
    from quadkit.ai.llm.clients.openai_compatible import (
        DeepSeekClient,
        FireworksClient,
        TogetherClient,
    )

    entries.append(
        {
            "name": "deepseek",
            "client_class": DeepSeekClient,
            "default_models": ["deepseek-chat", "deepseek-coder"],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.deepseek.com/v1",
            "docs_url": "https://api-docs.deepseek.com",
            "pricing_url": "https://www.deepseek.com/",
            "description": "DeepSeek — cost-efficient OpenAI-compatible inference provider",
        }
    )

    entries.append(
        {
            "name": "together",
            "client_class": TogetherClient,
            "default_models": [
                "meta-llama/Llama-3-8b-chat-hf",
                "mistralai/Mixtral-8x7B-Instruct-v0.1",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.together.xyz/v1",
            "docs_url": "https://docs.together.ai",
            "pricing_url": "https://www.together.ai/pricing",
            "description": "Together AI — OpenAI-compatible serving for open-source and fine-tuned models",
        }
    )

    entries.append(
        {
            "name": "fireworks",
            "client_class": FireworksClient,
            "default_models": [
                "accounts/fireworks/models/llama-v3-70b-instruct",
                "accounts/fireworks/models/mixtral-8x7b-instruct",
            ],
            "supports_streaming": True,
            "supports_tools": True,
            "supports_vision": False,
            "base_url": "https://api.fireworks.ai/inference/v1",
            "docs_url": "https://docs.fireworks.ai",
            "pricing_url": "https://fireworks.ai/pricing",
            "description": "Fireworks AI — optimized OpenAI-compatible inference platform",
        }
    )

    return tuple(entries)
