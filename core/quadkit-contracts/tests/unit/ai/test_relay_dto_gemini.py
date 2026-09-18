"""Tests for the Gemini generateContent wire DTO."""
from __future__ import annotations

from quadkit.contracts.ai.relay.dto import (
    GeminiCandidate,
    GeminiContent,
    GeminiGroundingMetadata,
    GeminiPart,
    GeminiPromptFeedback,
    GeminiRequest,
    GeminiResponse,
    GeminiSafetyRating,
    GeminiUsageMetadata,
)


class TestGeminiDto:
    def test_part_to_dict(self) -> None:
        part = GeminiPart(text="hi")
        assert part.to_dict() == {"text": "hi"}

    def test_content_to_dict(self) -> None:
        content = GeminiContent(role="user", parts=[GeminiPart(text="hi")])
        assert content.to_dict() == {"role": "user", "parts": [{"text": "hi"}]}

    def test_request_generation_config(self) -> None:
        request = GeminiRequest.from_dict(
            {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}
        )
        assert request.contents[0].role == "user"
        assert request.generation_config == {}

    def test_request_to_dict_omits_empty_generation_config(self) -> None:
        request = GeminiRequest(contents=[GeminiContent(role="user", parts=[GeminiPart(text="hi")])])
        data = request.to_dict()
        assert data == {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}

    def test_system_instruction_uses_wire_casing(self) -> None:
        """to_dict emits systemInstruction; from_dict accepts both casings."""
        request = GeminiRequest(
            contents=[GeminiContent(role="user", parts=[GeminiPart(text="hi")])],
            system_instruction={"parts": [{"text": "You are helpful"}]},
        )
        data = request.to_dict()
        assert data["systemInstruction"] == {"parts": [{"text": "You are helpful"}]}
        assert "system_instruction" not in data
        parsed = GeminiRequest.from_dict(
            {"contents": [], "systemInstruction": {"parts": [{"text": "x"}]}}
        )
        assert parsed.system_instruction == {"parts": [{"text": "x"}]}
        compat = GeminiRequest.from_dict(
            {"contents": [], "system_instruction": {"parts": [{"text": "y"}]}}
        )
        assert compat.system_instruction == {"parts": [{"text": "y"}]}

    def test_request_carries_safety_and_tool_config(self) -> None:
        """safetySettings and toolConfig survive the round trip."""
        request = GeminiRequest.from_dict(
            {
                "contents": [],
                "safetySettings": [{"category": "HARM_CATEGORY_X", "threshold": "BLOCK_NONE"}],
                "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
            }
        )
        assert request.safety_settings == [
            {"category": "HARM_CATEGORY_X", "threshold": "BLOCK_NONE"}
        ]
        assert request.tool_config == {"functionCallingConfig": {"mode": "ANY"}}
        data = request.to_dict()
        assert data["safetySettings"][0]["threshold"] == "BLOCK_NONE"
        assert data["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"

    def test_part_casing_and_thought_signature(self) -> None:
        """inlineData/functionCall/functionResponse/thoughtSignature use wire casing."""
        part = GeminiPart(
            inline_data={"mime_type": "image/png", "data": "AAAA"},
            thought=True,
            thought_signature="sig_1",
        )
        data = part.to_dict()
        assert data["inlineData"] == {"mime_type": "image/png", "data": "AAAA"}
        assert data["thought"] is True
        assert data["thoughtSignature"] == "sig_1"
        parsed = GeminiPart.from_dict(
            {"thought": True, "thoughtSignature": "sig_2", "fileData": {"fileUri": "gs://x"}}
        )
        assert parsed.thought_signature == "sig_2"
        assert parsed.file_data == {"fileUri": "gs://x"}
        assert parsed.to_dict()["fileData"] == {"fileUri": "gs://x"}


class TestGeminiResponseDto:
    def test_response_round_trip(self) -> None:
        response = GeminiResponse(
            candidates=[
                GeminiCandidate(
                    content=GeminiContent(role="model", parts=[GeminiPart(text="Hi")]),
                    finish_reason="STOP",
                    safety_ratings=[
                        GeminiSafetyRating(category="HARM_CATEGORY_HARASSMENT", probability="NEGLIGIBLE")
                    ],
                    grounding_metadata=GeminiGroundingMetadata(web_search_queries=["paris"]),
                    token_count=15,
                )
            ],
            prompt_feedback=GeminiPromptFeedback(block_reason=None),
            usage_metadata=GeminiUsageMetadata(
                prompt_token_count=10,
                candidates_token_count=5,
                total_token_count=15,
                thoughts_token_count=2,
            ),
            model_version="gemini-2.0-flash-001",
            passthrough={"createTime": "2026-01-01T00:00:00Z"},
        )
        data = response.to_dict()
        assert data["candidates"][0]["content"]["parts"] == [{"text": "Hi"}]
        assert data["candidates"][0]["finishReason"] == "STOP"
        assert data["candidates"][0]["safetyRatings"][0]["category"] == "HARM_CATEGORY_HARASSMENT"
        assert data["candidates"][0]["groundingMetadata"]["webSearchQueries"] == ["paris"]
        assert data["candidates"][0]["tokenCount"] == 15
        assert data["usageMetadata"]["thoughtsTokenCount"] == 2
        assert data["modelVersion"] == "gemini-2.0-flash-001"
        assert data["createTime"] == "2026-01-01T00:00:00Z"

    def test_response_from_dict(self) -> None:
        response = GeminiResponse.from_dict(
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": "Hi"}]},
                        "finishReason": "STOP",
                        "index": 0,
                    }
                ],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1, "totalTokenCount": 2},
                "modelVersion": "gemini-2.0-flash-001",
            }
        )
        assert response.candidates[0].content is not None
        assert response.candidates[0].content.parts[0].text == "Hi"
        assert response.candidates[0].finish_reason == "STOP"
        assert response.usage_metadata is not None
        assert response.usage_metadata.total_token_count == 2

    def test_stream_chunk_shares_response_shape(self) -> None:
        """Gemini stream chunks use the response schema with passthrough."""
        chunk = GeminiResponse.from_dict(
            {"candidates": [{"content": {"role": "model", "parts": [{"text": "Hel"}]}}],
             "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 0, "totalTokenCount": 1}}
        )
        data = chunk.to_dict()
        assert data["candidates"][0]["content"]["parts"] == [{"text": "Hel"}]
        assert data["usageMetadata"]["totalTokenCount"] == 1
