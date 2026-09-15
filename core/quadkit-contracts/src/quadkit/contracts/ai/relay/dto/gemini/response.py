"""Gemini wire DTO family — response DTOs and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.gemini.parts import GeminiContent


@dataclass(frozen=True)
class GeminiSafetyRating:
    """A Gemini safety rating entry.

    Attributes:
        category: Harm category.
        probability: Probability level.
        blocked: Whether the content was blocked.
        severity: Severity level, or ``None``.
        probability_score: Raw probability score, or ``None``.
        severity_score: Raw severity score, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    category: str = ""
    probability: str = ""
    blocked: bool = False
    severity: str | None = None
    probability_score: float | None = None
    severity_score: float | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.category:
            data["category"] = self.category
        if self.probability:
            data["probability"] = self.probability
        if self.blocked:
            data["blocked"] = True
        if self.severity is not None:
            data["severity"] = self.severity
        if self.probability_score is not None:
            data["probabilityScore"] = self.probability_score
        if self.severity_score is not None:
            data["severityScore"] = self.severity_score
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiSafetyRating:
        """Build a rating from a wire dict, capturing unknown keys."""
        known = {
            "category",
            "probability",
            "blocked",
            "severity",
            "probabilityScore",
            "severityScore",
        }
        return cls(
            category=data.get("category", ""),
            probability=data.get("probability", ""),
            blocked=bool(data.get("blocked", False)),
            severity=data.get("severity"),
            probability_score=data.get("probabilityScore"),
            severity_score=data.get("severityScore"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiGroundingMetadata:
    """Gemini grounding metadata for a candidate.

    Attributes:
        grounding_chunks: Raw grounding chunk list.
        grounding_supports: Raw grounding support list.
        web_search_queries: Web search queries, if any.
        retrieval_metadata: Raw retrieval metadata list.
        passthrough: Unknown fields preserved verbatim.
    """

    grounding_chunks: list[dict[str, Any]] = field(default_factory=list)
    grounding_supports: list[dict[str, Any]] = field(default_factory=list)
    web_search_queries: list[str] = field(default_factory=list)
    retrieval_metadata: list[dict[str, Any]] = field(default_factory=list)
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.grounding_chunks:
            data["groundingChunks"] = self.grounding_chunks
        if self.grounding_supports:
            data["groundingSupports"] = self.grounding_supports
        if self.web_search_queries:
            data["webSearchQueries"] = self.web_search_queries
        if self.retrieval_metadata:
            data["retrievalMetadata"] = self.retrieval_metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiGroundingMetadata:
        """Build metadata from a wire dict, capturing unknown keys."""
        known = {
            "groundingChunks",
            "groundingSupports",
            "webSearchQueries",
            "retrievalMetadata",
        }
        return cls(
            grounding_chunks=data.get("groundingChunks", []),
            grounding_supports=data.get("groundingSupports", []),
            web_search_queries=data.get("webSearchQueries", []),
            retrieval_metadata=data.get("retrievalMetadata", []),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiCandidate:
    """One candidate in a Gemini response.

    Attributes:
        content: Candidate content, or ``None``.
        finish_reason: ``STOP``, ``MAX_TOKENS``, ``SAFETY``, etc.
        index: Candidate index.
        safety_ratings: Safety ratings, or ``None``.
        grounding_metadata: Grounding metadata, or ``None``.
        citation_metadata: Raw citation metadata, or ``None``.
        token_count: Token count for the candidate.
        avg_logprobs: Average log probability.
        passthrough: Unknown fields preserved verbatim.
    """

    content: GeminiContent | None = None
    finish_reason: str | None = None
    index: int | None = None
    safety_ratings: list[GeminiSafetyRating] | None = None
    grounding_metadata: GeminiGroundingMetadata | None = None
    citation_metadata: dict[str, Any] | None = None
    token_count: int | None = None
    avg_logprobs: float | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.content is not None:
            data["content"] = self.content.to_dict()
        if self.finish_reason is not None:
            data["finishReason"] = self.finish_reason
        if self.index is not None:
            data["index"] = self.index
        if self.safety_ratings is not None:
            data["safetyRatings"] = [r.to_dict() for r in self.safety_ratings]
        if self.grounding_metadata is not None:
            data["groundingMetadata"] = self.grounding_metadata.to_dict()
        if self.citation_metadata is not None:
            data["citationMetadata"] = self.citation_metadata
        if self.token_count is not None:
            data["tokenCount"] = self.token_count
        if self.avg_logprobs is not None:
            data["avgLogprobs"] = self.avg_logprobs
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiCandidate:
        """Build a candidate from a wire dict, capturing unknown keys."""
        known = {
            "content",
            "finishReason",
            "index",
            "safetyRatings",
            "groundingMetadata",
            "citationMetadata",
            "tokenCount",
            "avgLogprobs",
        }
        content = data.get("content")
        safety = data.get("safetyRatings")
        grounding = data.get("groundingMetadata")
        return cls(
            content=GeminiContent.from_dict(content)
            if isinstance(content, dict)
            else None,
            finish_reason=data.get("finishReason"),
            index=data.get("index"),
            safety_ratings=(
                [GeminiSafetyRating.from_dict(r) for r in safety]
                if isinstance(safety, list)
                else None
            ),
            grounding_metadata=(
                GeminiGroundingMetadata.from_dict(grounding)
                if isinstance(grounding, dict)
                else None
            ),
            citation_metadata=data.get("citationMetadata"),
            token_count=data.get("tokenCount"),
            avg_logprobs=data.get("avgLogprobs"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiUsageMetadata:
    """Gemini usage metadata.

    Attributes:
        prompt_token_count: Input tokens.
        candidates_token_count: Output tokens.
        total_token_count: Total tokens.
        cached_content_token_count: Cached input tokens, or ``None``.
        thoughts_token_count: Thinking tokens, or ``None``.
        tool_use_prompt_token_count: Tokens spent on tool-use prompt parts.
        prompt_tokens_details: Per-input-category details, or ``None``.
        tool_use_prompt_tokens_details: Per-tool-call details, or ``None``.
        candidates_tokens_details: Per-output-category details, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0
    cached_content_token_count: int | None = None
    thoughts_token_count: int | None = None
    tool_use_prompt_token_count: int = 0
    prompt_tokens_details: Any = None
    tool_use_prompt_tokens_details: Any = None
    candidates_tokens_details: Any = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {
            **self.passthrough,
            "promptTokenCount": self.prompt_token_count,
            "toolUsePromptTokenCount": self.tool_use_prompt_token_count,
            "candidatesTokenCount": self.candidates_token_count,
            "totalTokenCount": self.total_token_count,
            "promptTokensDetails": self.prompt_tokens_details,
            "toolUsePromptTokensDetails": self.tool_use_prompt_tokens_details,
            "candidatesTokensDetails": self.candidates_tokens_details,
        }
        if self.cached_content_token_count is not None:
            data["cachedContentTokenCount"] = self.cached_content_token_count
        if self.thoughts_token_count is not None:
            data["thoughtsTokenCount"] = self.thoughts_token_count
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiUsageMetadata:
        """Build usage from a wire dict, capturing unknown keys."""
        known = {
            "promptTokenCount",
            "toolUsePromptTokenCount",
            "candidatesTokenCount",
            "totalTokenCount",
            "cachedContentTokenCount",
            "thoughtsTokenCount",
            "promptTokensDetails",
            "toolUsePromptTokensDetails",
            "candidatesTokensDetails",
        }
        return cls(
            prompt_token_count=data.get("promptTokenCount", 0),
            candidates_token_count=data.get("candidatesTokenCount", 0),
            total_token_count=data.get("totalTokenCount", 0),
            cached_content_token_count=data.get("cachedContentTokenCount"),
            thoughts_token_count=data.get("thoughtsTokenCount"),
            tool_use_prompt_token_count=data.get("toolUsePromptTokenCount", 0),
            prompt_tokens_details=data.get("promptTokensDetails"),
            tool_use_prompt_tokens_details=data.get("toolUsePromptTokensDetails"),
            candidates_tokens_details=data.get("candidatesTokensDetails"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiPromptFeedback:
    """Prompt-level feedback on a Gemini response.

    Attributes:
        block_reason: Block reason, or ``None``.
        safety_ratings: Safety ratings, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    block_reason: str | None = None
    safety_ratings: list[GeminiSafetyRating] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.block_reason is not None:
            data["blockReason"] = self.block_reason
        if self.safety_ratings is not None:
            data["safetyRatings"] = [r.to_dict() for r in self.safety_ratings]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiPromptFeedback:
        """Build feedback from a wire dict, capturing unknown keys."""
        known = {"blockReason", "safetyRatings"}
        safety = data.get("safetyRatings")
        return cls(
            block_reason=data.get("blockReason"),
            safety_ratings=(
                [GeminiSafetyRating.from_dict(r) for r in safety]
                if isinstance(safety, list)
                else None
            ),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiResponse:
    """Gemini ``generateContent`` response body (also used for stream chunks).

    Attributes:
        candidates: Candidate list.
        prompt_feedback: Prompt-level feedback, or ``None``.
        usage_metadata: Token usage, or ``None``.
        model_version: Model version, or ``None``.
        create_time: Response creation time, or ``None``.
        response_id: Response id, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    candidates: list[GeminiCandidate] = field(default_factory=list)
    prompt_feedback: GeminiPromptFeedback | None = None
    usage_metadata: GeminiUsageMetadata | None = None
    model_version: str | None = None
    create_time: str | None = None
    response_id: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.candidates:
            data["candidates"] = [c.to_dict() for c in self.candidates]
        if self.prompt_feedback is not None:
            data["promptFeedback"] = self.prompt_feedback.to_dict()
        if self.usage_metadata is not None:
            data["usageMetadata"] = self.usage_metadata.to_dict()
        if self.model_version is not None:
            data["modelVersion"] = self.model_version
        if self.create_time is not None:
            data["createTime"] = self.create_time
        if self.response_id is not None:
            data["responseId"] = self.response_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiResponse:
        """Build a response from a wire dict, capturing unknown keys."""
        known = {
            "candidates",
            "promptFeedback",
            "usageMetadata",
            "modelVersion",
            "createTime",
            "responseId",
        }
        feedback = data.get("promptFeedback")
        usage = data.get("usageMetadata")
        return cls(
            candidates=[
                GeminiCandidate.from_dict(c) for c in data.get("candidates", [])
            ],
            prompt_feedback=(
                GeminiPromptFeedback.from_dict(feedback)
                if isinstance(feedback, dict)
                else None
            ),
            usage_metadata=(
                GeminiUsageMetadata.from_dict(usage)
                if isinstance(usage, dict)
                else None
            ),
            model_version=data.get("modelVersion"),
            create_time=data.get("createTime"),
            response_id=data.get("responseId"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
