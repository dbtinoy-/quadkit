"""Tests for LLM constants - provider names, defaults, and metric identifiers."""

import pytest

from quadkit.ai.llm import constants as llm_constants


class TestVersion:
    def test_version_is_string(self) -> None:
        assert isinstance(llm_constants.__version__, str)

    def test_version_format(self) -> None:
        parts = llm_constants.__version__.split(".")
        assert len(parts) >= 2


class TestEnvironmentVariables:
    def test_env_prefix(self) -> None:
        assert llm_constants.ENV_PREFIX == "QK_AI_LLM__"

    def test_nested_delimiter(self) -> None:
        assert llm_constants.ENV_NESTED_DELIMITER == "__"


class TestProviderNames:
    def test_openai(self) -> None:
        assert llm_constants.PROVIDER_OPENAI == "openai"

    def test_anthropic(self) -> None:
        assert llm_constants.PROVIDER_ANTHROPIC == "anthropic"

    def test_ollama(self) -> None:
        assert llm_constants.PROVIDER_OLLAMA == "ollama"

    def test_cohere(self) -> None:
        assert llm_constants.PROVIDER_COHERE == "cohere"

    def test_groq(self) -> None:
        assert llm_constants.PROVIDER_GROQ == "groq"

    def test_mistral(self) -> None:
        assert llm_constants.PROVIDER_MISTRAL == "mistral"

    def test_openrouter(self) -> None:
        assert llm_constants.PROVIDER_OPENROUTER == "openrouter"

    def test_all_providers_are_strings(self) -> None:
        providers = [
            llm_constants.PROVIDER_OPENAI,
            llm_constants.PROVIDER_ANTHROPIC,
            llm_constants.PROVIDER_OLLAMA,
            llm_constants.PROVIDER_COHERE,
            llm_constants.PROVIDER_GROQ,
            llm_constants.PROVIDER_MISTRAL,
            llm_constants.PROVIDER_OPENROUTER,
        ]
        assert all(isinstance(p, str) for p in providers)

    def test_all_providers_unique(self) -> None:
        providers = [
            llm_constants.PROVIDER_OPENAI,
            llm_constants.PROVIDER_ANTHROPIC,
            llm_constants.PROVIDER_OLLAMA,
            llm_constants.PROVIDER_COHERE,
            llm_constants.PROVIDER_GROQ,
            llm_constants.PROVIDER_MISTRAL,
            llm_constants.PROVIDER_OPENROUTER,
        ]
        assert len(providers) == len(set(providers))


class TestDefaults:
    def test_default_temperature(self) -> None:
        assert llm_constants.DEFAULT_TEMPERATURE == 0.7

    def test_default_max_tokens(self) -> None:
        assert llm_constants.DEFAULT_MAX_TOKENS == 2048

    def test_default_timeout_s(self) -> None:
        assert llm_constants.DEFAULT_TIMEOUT_S == 30

    def test_default_max_retries(self) -> None:
        assert llm_constants.DEFAULT_MAX_RETRIES == 3

    def test_temperature_is_float(self) -> None:
        assert isinstance(llm_constants.DEFAULT_TEMPERATURE, float)

    def test_max_tokens_is_int(self) -> None:
        assert isinstance(llm_constants.DEFAULT_MAX_TOKENS, int)

    def test_timeout_is_int(self) -> None:
        assert isinstance(llm_constants.DEFAULT_TIMEOUT_S, int)

    def test_max_retries_is_int(self) -> None:
        assert isinstance(llm_constants.DEFAULT_MAX_RETRIES, int)


class TestMetricNames:
    def test_llm_requests_total(self) -> None:
        assert llm_constants.METRIC_LLM_REQUESTS_TOTAL == "ai.llm.requests.total"

    def test_llm_request_duration_ms(self) -> None:
        assert llm_constants.METRIC_LLM_REQUEST_DURATION_MS == "ai.llm.request.duration_ms"

    def test_llm_tokens_input(self) -> None:
        assert llm_constants.METRIC_LLM_TOKENS_INPUT == "ai.llm.tokens.input"

    def test_llm_tokens_output(self) -> None:
        assert llm_constants.METRIC_LLM_TOKENS_OUTPUT == "ai.llm.tokens.output"

    def test_llm_cache_hits(self) -> None:
        assert llm_constants.METRIC_LLM_CACHE_HITS == "ai.llm.cache.hits"

    def test_all_metric_names_are_strings(self) -> None:
        metrics = [
            llm_constants.METRIC_LLM_REQUESTS_TOTAL,
            llm_constants.METRIC_LLM_REQUEST_DURATION_MS,
            llm_constants.METRIC_LLM_TOKENS_INPUT,
            llm_constants.METRIC_LLM_TOKENS_OUTPUT,
            llm_constants.METRIC_LLM_CACHE_HITS,
        ]
        assert all(isinstance(m, str) for m in metrics)

    def test_all_metric_names_unique(self) -> None:
        metrics = [
            llm_constants.METRIC_LLM_REQUESTS_TOTAL,
            llm_constants.METRIC_LLM_REQUEST_DURATION_MS,
            llm_constants.METRIC_LLM_TOKENS_INPUT,
            llm_constants.METRIC_LLM_TOKENS_OUTPUT,
            llm_constants.METRIC_LLM_CACHE_HITS,
        ]
        assert len(metrics) == len(set(metrics))

    def test_metric_names_start_with_prefix(self) -> None:
        prefix = "ai.llm."
        metrics = [
            llm_constants.METRIC_LLM_REQUESTS_TOTAL,
            llm_constants.METRIC_LLM_REQUEST_DURATION_MS,
            llm_constants.METRIC_LLM_TOKENS_INPUT,
            llm_constants.METRIC_LLM_TOKENS_OUTPUT,
            llm_constants.METRIC_LLM_CACHE_HITS,
        ]
        assert all(m.startswith(prefix) for m in metrics)


class TestExports:
    def test_all_exports(self) -> None:
        expected = {
            "DEFAULT_MAX_RETRIES",
            "DEFAULT_MAX_TOKENS",
            "DEFAULT_TEMPERATURE",
            "DEFAULT_TIMEOUT_S",
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
            "METRIC_LLM_CACHE_HITS",
            "METRIC_LLM_REQUESTS_TOTAL",
            "METRIC_LLM_REQUEST_DURATION_MS",
            "METRIC_LLM_TOKENS_INPUT",
            "METRIC_LLM_TOKENS_OUTPUT",
            "PROVIDER_ANTHROPIC",
            "PROVIDER_COHERE",
            "PROVIDER_GROQ",
            "PROVIDER_MISTRAL",
            "PROVIDER_OLLAMA",
            "PROVIDER_OPENAI",
            "PROVIDER_OPENROUTER",
            "__version__",
        }
        assert set(llm_constants.__all__) == expected