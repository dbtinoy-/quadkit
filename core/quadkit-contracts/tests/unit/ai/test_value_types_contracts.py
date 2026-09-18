"""Tests for AI value-type contracts (chunks, thinking, models, vector, workflow, rag, evaluation)."""

from dataclasses import FrozenInstanceError
from typing import Any

from quadkit.contracts.ai.chunks import Chunk, ContextChunk
from quadkit.contracts.ai.evaluation import (
    EvaluationDataset,
    EvaluationResult,
    EvaluationSample,
    EvaluationScoreType,
    RunReport,
)
from quadkit.contracts.ai.models import ModelRequest, ModelResponse
from quadkit.contracts.ai.rag import RAGContext, RAGResponse
from quadkit.contracts.ai.thinking import ThinkingConfig, ThinkingResult
from quadkit.contracts.ai.vector import (
    Document,
    DocumentProtocol,
    EmbeddingResult,
    RAGSearchResult,
    SearchResultProtocol,
)
from quadkit.contracts.ai.workflow import WorkflowResult


class TestChunkTypes:
    def test_defaults(self) -> None:
        chunk = Chunk(text="hello")
        assert chunk.text == "hello"
        assert chunk.source == "unknown"
        assert chunk.metadata == {}
        assert chunk.score is None
        assert chunk.embedding is None

    def test_frozen(self) -> None:
        chunk = Chunk(text="hello")
        try:
            chunk.text = "other"
        except FrozenInstanceError:
            pass
        else:
            msg = "Chunk must be frozen"
            raise AssertionError(msg)

    def test_metadata_isolation(self) -> None:
        a = Chunk(text="a")
        b = Chunk(text="b")
        a.metadata["k"] = "v"
        assert b.metadata == {}

    def test_context_chunk_extends_chunk(self) -> None:
        context = ContextChunk(text="hello", source="doc.md")
        assert isinstance(context, Chunk)
        assert context.rank == 0
        assert context.source == "doc.md"

    def test_context_chunk_rank(self) -> None:
        context = ContextChunk(text="hello", rank=3)
        assert context.rank == 3


class TestThinkingTypes:
    def test_config_defaults(self) -> None:
        config = ThinkingConfig()
        assert config.suppress is False
        assert config.budget_tokens == 10_000
        assert config.level is None
        assert config.effort is None

    def test_config_frozen(self) -> None:
        config = ThinkingConfig()
        try:
            config.budget_tokens = 1
        except FrozenInstanceError:
            pass
        else:
            msg = "ThinkingConfig must be frozen"
            raise AssertionError(msg)

    def test_result_defaults(self) -> None:
        result = ThinkingResult(content="thinking...")
        assert result.signature is None
        assert result.tokens is None

    def test_result_with_anthropic_fields(self) -> None:
        result = ThinkingResult(content="x", signature="sig", tokens=123)
        assert result.signature == "sig"
        assert result.tokens == 123


class TestModelTypes:
    def test_request_defaults(self) -> None:
        request = ModelRequest(prompt="say hi")
        assert request.prompt == "say hi"
        assert request.model_id is None
        assert request.temperature is None
        assert request.max_tokens is None
        assert request.top_p is None
        assert request.top_k is None
        assert request.required_capabilities is None
        assert request.extra_params == {}

    def test_request_extra_params_isolation(self) -> None:
        a = ModelRequest(prompt="a")
        b = ModelRequest(prompt="b")
        a.extra_params["seed"] = 1
        assert b.extra_params == {}

    def test_response_defaults(self) -> None:
        response = ModelResponse(content="out")
        assert response.content == "out"
        assert response.tokens_used == 0
        assert response.stop_reason is None
        assert response.extra_metadata == {}


class TestVectorValueTypes:
    def test_document_defaults(self) -> None:
        doc = Document(text="body")
        assert doc.text == "body"
        assert doc.metadata == {}
        assert doc.id is None
        assert doc.embedding is None

    def test_document_satisfies_protocol(self) -> None:
        doc = Document(text="body", id="d1")
        assert isinstance(doc, DocumentProtocol)
        assert doc.id == "d1"

    def test_embedding_result_frozen(self) -> None:
        result = EmbeddingResult(vectors=[[0.1, 0.2]], model="m", tokens=5)
        assert result.vectors == [[0.1, 0.2]]
        assert result.model == "m"
        assert result.tokens == 5
        try:
            result.model = "other"
        except FrozenInstanceError:
            pass
        else:
            msg = "EmbeddingResult must be frozen"
            raise AssertionError(msg)

    def test_rag_search_result_satisfies_protocol(self) -> None:
        result = RAGSearchResult(document=Document(text="body"), score=0.9)
        assert isinstance(result, SearchResultProtocol)
        assert isinstance(result.document, DocumentProtocol)

    def test_rag_search_result_text_delegates_to_document(self) -> None:
        result = RAGSearchResult(document=Document(text="body"), score=0.9)
        assert result.text == "body"

    def test_rag_search_result_defaults_and_immutable(self) -> None:
        result = RAGSearchResult(document=Document(text="body"), score=0.9)
        assert result.rank == 0
        assert result.metadata == {}
        try:
            result.score = 0.1
        except FrozenInstanceError:
            pass
        else:
            msg = "RAGSearchResult must be frozen"
            raise AssertionError(msg)


class TestWorkflowResult:
    def test_get_existing_key(self) -> None:
        result = WorkflowResult(final_state={"a": 1}, output="done")
        assert result.get("a") == 1

    def test_get_missing_key_default(self) -> None:
        result = WorkflowResult(final_state={"a": 1})
        assert result.get("missing") is None
        assert result.get("missing", "fallback") == "fallback"

    def test_trace_default(self) -> None:
        result = WorkflowResult(final_state={})
        assert result.trace == []
        assert result.output is None

    def test_frozen(self) -> None:
        result = WorkflowResult(final_state={"a": 1})
        try:
            result.output = "x"
        except FrozenInstanceError:
            pass
        else:
            msg = "WorkflowResult must be frozen"
            raise AssertionError(msg)


class TestRAGContextResponse:
    def test_context_defaults(self) -> None:
        context = RAGContext(query="why?")
        assert context.query == "why?"
        assert context.config is None
        assert context.filters is None
        assert context.session_id is None

    def test_response_defaults(self) -> None:
        response = RAGResponse(answer="a", sources=[])
        assert response.answer == "a"
        assert response.sources == []
        assert response.citations is None
        assert response.confidence is None


class TestEvaluationTypes:
    def test_score_type_values(self) -> None:
        assert EvaluationScoreType.EXACT_MATCH.value == "exact_match"
        assert EvaluationScoreType.PARTIAL_MATCH.value == "partial_match"
        assert EvaluationScoreType.SEMANTIC_SIMILARITY.value == "semantic_similarity"
        assert EvaluationScoreType.STRING_DISTANCE.value == "string_distance"
        assert EvaluationScoreType.TRAJECTORY_FIDELITY.value == "trajectory_fidelity"
        assert EvaluationScoreType.CUSTOM.value == "custom"

    def test_sample_output_defaults_empty(self) -> None:
        sample = EvaluationSample(id="s1", input="in", reference="ref", metadata={})
        assert sample.output == ""

    def test_dataset_and_report_frozen(self) -> None:
        dataset = EvaluationDataset(name="d", samples=[], metadata={})
        report = RunReport(
            dataset_name="d",
            evaluator_name="e",
            total_samples=0,
            passed_samples=0,
            average_score=0.0,
            results=[],
            metadata={},
        )
        for obj in (dataset, report):
            field_name: Any = "name" if isinstance(obj, EvaluationDataset) else "dataset_name"
            try:
                setattr(obj, field_name, "other")
            except FrozenInstanceError:
                pass
            else:
                msg = f"{type(obj).__name__} must be frozen"
                raise AssertionError(msg)

    def test_result_carries_metrics(self) -> None:
        result = EvaluationResult(
            score=0.8,
            score_type=EvaluationScoreType.SEMANTIC_SIMILARITY,
            feedback="close",
            metrics={"sim": 0.8},
        )
        assert result.score == 0.8
        assert result.metrics == {"sim": 0.8}
