"""Tests for the AI test cluster: bed, client, and data.

Covers :class:`AITestData` recording/mock helpers, :class:`AITestClient`
token-budget enforcement and operation wrappers, and :class:`AITestBed`
mock service accessors.
"""

from __future__ import annotations

import pytest

from quadkit.testing.clients.ai.bed import AITestBed
from quadkit.testing.clients.ai.client import AITestClient
from quadkit.testing.clients.ai.data import AITestData
from quadkit.testing.exceptions import TokenBudgetExceededError


# ---------------------------------------------------------------------------
# AITestData
# ---------------------------------------------------------------------------


def test_test_data_records_all_operation_kinds() -> None:
    data = AITestData(prefix="x")
    assert data.prefix == "x"

    data.add_llm_completion({"prompt": "p"})
    data.add_vector_search({"query": "q"})
    data.add_ml_prediction({"input": 1})
    data.add_pipeline_operation({"stage": "s"})
    data.add_rag_operation({"doc": "d"})
    data.add_agent_operation({"action": "a"})
    data.record_time_advance(1.5)

    assert len(data._llm_completions) == 1
    assert len(data._vector_searches) == 1
    assert len(data._ml_predictions) == 1
    assert len(data._pipeline_operations) == 1
    assert len(data._rag_operations) == 1
    assert len(data._agent_operations) == 1
    assert data._time_advances == [1.5]


def test_test_data_mock_responses_and_clear() -> None:
    data = AITestData()
    assert data.get_mock_response("llm") is None

    data.set_mock_response("llm", {"response": "hi", "tokens": 3})
    assert data.get_mock_response("llm") == {"response": "hi", "tokens": 3}

    data.add_llm_completion({"prompt": "p"})
    data.clear()
    assert data._llm_completions == []
    assert data.get_mock_response("llm") is None


# ---------------------------------------------------------------------------
# AITestClient — token budget
# ---------------------------------------------------------------------------


def _client_with_budget(budget: int) -> AITestClient:
    return AITestClient(AITestBed(), max_tokens_per_run=budget)


def test_token_budget_enforcement() -> None:
    client = _client_with_budget(10)
    assert client.token_budget == 10
    assert client.tokens_used == 0

    client._charge_tokens(6)
    assert client.tokens_used == 6
    client._charge_tokens(4)
    assert client.tokens_used == 10

    with pytest.raises(TokenBudgetExceededError):
        client._charge_tokens(1)

    client.reset_token_budget()
    assert client.tokens_used == 0


def test_token_budget_zero_means_unlimited() -> None:
    client = _client_with_budget(0)
    # Unlimited: no enforcement (and no accounting) regardless of size.
    client._charge_tokens(10_000)
    assert client.tokens_used == 0


# ---------------------------------------------------------------------------
# AITestClient — operation wrappers
# ---------------------------------------------------------------------------


async def test_complete_with_llm_uses_mock_and_records() -> None:
    client = _client_with_budget(100)
    client.test_data.set_mock_response("llm", {"response": "hello", "tokens": 5})

    record = await client.complete_with_llm("tell me a joke", extra="x")
    assert record["prompt"] == "tell me a joke"
    assert record["response"] == {"response": "hello", "tokens": 5}
    assert record["extra"] == "x"
    assert client.tokens_used == 5
    client.assert_llm_completions_count(1)


async def test_complete_with_llm_estimates_tokens_when_unconfigured() -> None:
    client = _client_with_budget(100)
    # ceil(5 words * 1.3) = 7 tokens
    await client.complete_with_llm("one two three four five")
    assert client.tokens_used == 7
    client.assert_llm_completions_count(1)


async def test_complete_with_llm_respects_budget() -> None:
    client = _client_with_budget(3)
    client.test_data.set_mock_response("llm", {"response": "x", "tokens": 10})
    with pytest.raises(TokenBudgetExceededError):
        await client.complete_with_llm("anything")
    client.assert_llm_completions_count(0)


async def test_search_vector_store_mock_and_default() -> None:
    client = _client_with_budget(0)
    record = await client.search_vector_store("find cats")
    assert record["results"] == {"results": []}
    client.assert_vector_searches_count(1)

    client.test_data.set_mock_response("vector", {"results": [{"id": 1}]})
    record2 = await client.search_vector_store("find dogs", top=2)
    assert record2["results"] == {"results": [{"id": 1}]}
    assert record2["top"] == 2
    client.assert_vector_searches_count(2)


async def test_predict_with_ml_mock_and_default() -> None:
    client = _client_with_budget(0)
    record = await client.predict_with_ml([1, 2, 3])
    assert record["output"] == {"output": None, "confidence": 0.0}
    client.assert_ml_predictions_count(1)

    client.test_data.set_mock_response("ml", {"output": "cat", "confidence": 0.9})
    record2 = await client.predict_with_ml([4, 5], model="m")
    assert record2["output"] == {"output": "cat", "confidence": 0.9}
    assert record2["model"] == "m"
    client.assert_ml_predictions_count(2)


def test_assertion_helpers_fail_on_mismatch() -> None:
    client = _client_with_budget(0)
    with pytest.raises(AssertionError, match="LLM completions"):
        client.assert_llm_completions_count(1)
    with pytest.raises(AssertionError, match="vector searches"):
        client.assert_vector_searches_count(1)
    with pytest.raises(AssertionError, match="ML predictions"):
        client.assert_ml_predictions_count(1)


# ---------------------------------------------------------------------------
# AITestBed
# ---------------------------------------------------------------------------


def test_bed_create_test_client_and_test_data() -> None:
    bed = AITestBed(name="ai-bed")
    assert bed.test_data is not None
    client = bed.create_test_client(max_tokens_per_run=42)
    assert isinstance(client, AITestClient)
    assert client.test_bed is bed
    assert client.token_budget == 42


def test_bed_mock_clients_are_cached_singletons() -> None:
    bed = AITestBed()
    assert bed.mock_llm is bed.mock_llm
    assert bed.mock_vector_store is bed.mock_vector_store
    assert bed.mock_ml_predictor is bed.mock_ml_predictor


async def test_bed_mock_llm_complete() -> None:
    bed = AITestBed()
    result = await bed.mock_llm.complete("prompt")
    assert result.content == "Mock response"
    assert result.model == "mock-model"
    assert result.usage.total_tokens == 10


async def test_bed_mock_vector_store_add_and_search() -> None:
    bed = AITestBed()
    added = await bed.mock_vector_store.add(["v1"])
    assert added == ["doc1", "doc2", "doc3"]

    results = await bed.mock_vector_store.search("query")
    assert len(results) == 2
    assert results[0].document.text == "Result 1"
    assert results[0].score == 0.95


async def test_bed_mock_ml_predictor_predict() -> None:
    bed = AITestBed()
    prediction = await bed.mock_ml_predictor.predict([1])
    assert prediction.result == "positive"
    assert prediction.confidence == 0.95


async def test_bed_async_accessors() -> None:
    bed = AITestBed()
    assert await bed.get_llm_client() is bed.mock_llm
    assert await bed.get_vector_store() is bed.mock_vector_store
    assert await bed.get_ml_predictor() is bed.mock_ml_predictor
