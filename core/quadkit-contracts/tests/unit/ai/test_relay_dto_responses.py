"""Tests for the OpenAI Responses wire DTO."""
from __future__ import annotations

from quadkit.contracts.ai.relay.dto import (
    ResponsesEvent,
    ResponsesIncompleteDetails,
    ResponsesItem,
    ResponsesRequest,
    ResponsesResponse,
    ResponsesUsage,
)


class TestResponsesDto:
    def test_input_message_item(self) -> None:
        item = ResponsesItem.from_dict(
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "hi"}]}
        )
        assert item.type == "message"
        assert item.role == "user"

    def test_request_to_dict(self) -> None:
        request = ResponsesRequest(model="gpt-4o", input=[])
        data = request.to_dict()
        assert data == {"model": "gpt-4o", "input": [], "stream": False}

    def test_response_to_dict(self) -> None:
        response = ResponsesResponse(
            id="resp_1",
            model="gpt-4o",
            output=[ResponsesItem(type="message", role="assistant")],
        )
        data = response.to_dict()
        assert data["id"] == "resp_1"
        assert data["output"][0]["type"] == "message"

    def test_request_carries_responses_fields(self) -> None:
        """parallel_tool_calls, reasoning, text, service_tier, include survive."""
        request = ResponsesRequest.from_dict(
            {
                "model": "gpt-4o",
                "input": [],
                "parallel_tool_calls": False,
                "reasoning": {"effort": "low"},
                "text": {"format": {"type": "json_schema", "name": "x"}},
                "service_tier": "flex",
                "include": ["reasoning.summary_text"],
            }
        )
        assert request.parallel_tool_calls is False
        assert request.reasoning == {"effort": "low"}
        assert request.text == {"format": {"type": "json_schema", "name": "x"}}
        assert request.service_tier == "flex"
        assert request.include == ["reasoning.summary_text"]

    def test_response_carries_incomplete_details_and_usage(self) -> None:
        """created_at, incomplete_details, and typed usage survive."""
        response = ResponsesResponse.from_dict(
            {
                "id": "resp_2",
                "object": "response",
                "created_at": 123,
                "model": "gpt-4o",
                "output": [],
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "input_tokens_details": {"cached_tokens": 3},
                },
            }
        )
        assert response.created_at == 123
        assert response.status == "incomplete"
        assert response.incomplete_details is not None
        assert response.incomplete_details.reason == "max_output_tokens"
        assert response.usage is not None
        assert response.usage.total_tokens == 15
        assert response.usage.input_tokens_details == {"cached_tokens": 3}

    def test_usage_derives_total(self) -> None:
        usage = ResponsesUsage(input_tokens=2, output_tokens=3)
        assert usage.to_dict()["total_tokens"] == 5


class TestResponsesEvents:
    def test_response_created_event(self) -> None:
        event = ResponsesEvent.from_dict(
            {
                "type": "response.created",
                "sequence_number": 0,
                "response": {
                    "id": "resp_1",
                    "object": "response",
                    "created_at": 123,
                    "model": "gpt-4o",
                    "output": [],
                    "status": "in_progress",
                },
            }
        )
        assert event.type == "response.created"
        assert event.response is not None
        assert event.response.id == "resp_1"

    def test_output_text_delta_event(self) -> None:
        event = ResponsesEvent.from_dict(
            {
                "type": "response.output_text.delta",
                "sequence_number": 4,
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": "Hel",
            }
        )
        assert event.item_id == "msg_1"
        assert event.output_index == 0
        assert event.content_index == 0
        assert event.delta == "Hel"

    def test_function_call_arguments_delta_event(self) -> None:
        event = ResponsesEvent.from_dict(
            {
                "type": "response.function_call_arguments.delta",
                "sequence_number": 5,
                "item_id": "fc_1",
                "output_index": 1,
                "delta": '{"city":',
            }
        )
        assert event.type == "response.function_call_arguments.delta"
        assert event.delta == '{"city":'

    def test_output_item_added_event(self) -> None:
        event = ResponsesEvent.from_dict(
            {
                "type": "response.output_item.added",
                "sequence_number": 1,
                "output_index": 0,
                "item": {"type": "reasoning", "id": "rs_1", "summary": [{"type": "summary_text", "text": "..."}]},
            }
        )
        assert event.item is not None
        assert event.item.type == "reasoning"
        assert event.item.summary == [{"type": "summary_text", "text": "..."}]

    def test_completed_event_round_trip(self) -> None:
        event = ResponsesEvent(
            type="response.completed",
            sequence_number=9,
            response=ResponsesResponse(id="resp_1", model="gpt-4o", output=[]),
        )
        data = event.to_dict()
        assert data["Type"] == "response.completed"
        assert data["Payload"]["type"] == "response.completed"
        assert data["Payload"]["sequence_number"] == 9
        assert data["Payload"]["response"]["model"] == "gpt-4o"

    def test_unknown_event_fields_retained(self) -> None:
        event = ResponsesEvent.from_dict(
            {"type": "response.in_progress", "sequence_number": 1, "extra": [1, 2]}
        )
        assert event.passthrough == {"extra": [1, 2]}

    def test_failed_event_carries_error(self) -> None:
        event = ResponsesEvent.from_dict(
            {"type": "response.failed", "sequence_number": 10,
             "error": {"code": "server_error", "message": "boom"}}
        )
        assert event.error == {"code": "server_error", "message": "boom"}
