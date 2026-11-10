"""Tests for InstructorExtractor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel
import pytest

from quadkit.ai.llm.exceptions import (
    ExtractionMaxRetriesError,
    LLMError,
)
from quadkit.ai.llm.extraction.extractor import InstructorExtractor
from quadkit.contracts.ai.llm import (
    ChatMessage,
    Completion,
    Role,
)
from quadkit.result import Err, Ok


class UserInfo(BaseModel):
    """Test model for extraction."""

    name: str
    age: int


class TestInstructorExtractor:
    """Test suite for InstructorExtractor."""

    @pytest.fixture
    def mock_llm_client(self) -> MagicMock:
        """Create a mock LLMClientProtocol."""
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_llm_client: MagicMock) -> InstructorExtractor:
        """Create an InstructorExtractor with a mock client."""
        return InstructorExtractor(llm_client=mock_llm_client, max_retries=3)

    @pytest.mark.asyncio
    async def test_extract_logs_do_not_include_schema_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quadkit.ai.llm.extraction.extractor as extractor_module
        from pydantic import create_model

        private_schema_name = "PrivateTenant42Schema"
        private_schema = create_model(private_schema_name, value=(str, ...))
        client = MagicMock()
        client.complete = AsyncMock(
            return_value=Ok(Completion(content='{"value":"ok"}', model="gpt-test"))
        )
        logger = MagicMock()
        monkeypatch.setattr(extractor_module, "logger", logger)
        extractor = InstructorExtractor(llm_client=client, max_retries=1)

        result = await extractor.extract(
            prompt="Extract a value",
            response_model=private_schema,
        )

        assert result.is_ok()
        assert private_schema_name not in repr(logger.mock_calls)

    @pytest.mark.asyncio
    async def test_extract_returns_ok_on_valid_json(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract returns Ok on valid JSON."""
        # Arrange
        valid_json = '{"name": "John", "age": 30}'
        completion = Completion(content=valid_json, model="gpt-4")
        mock_llm_client.complete.return_value = Ok(completion)

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_ok()
        user = result.unwrap()
        assert user.name == "John"
        assert user.age == 30
        mock_llm_client.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_returns_err_on_invalid_json(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract returns Err on invalid JSON."""
        # Arrange
        invalid_json = '{"name": "John", invalid}'
        completion = Completion(content=invalid_json, model="gpt-4")
        mock_llm_client.complete.return_value = Ok(completion)

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ExtractionMaxRetriesError)

    @pytest.mark.asyncio
    async def test_extract_retries_on_validation_error(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract retries on validation error then succeeds."""
        # Arrange
        invalid_data = Completion(content='{"name": "John"}', model="gpt-4")  # Missing age
        valid_data = Completion(content='{"name": "Jane", "age": 25}', model="gpt-4")

        # Mock to return invalid first, then valid
        mock_llm_client.complete.side_effect = [Ok(invalid_data), Ok(valid_data)]

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_ok()
        user = result.unwrap()
        assert user.name == "Jane"
        assert user.age == 25
        assert mock_llm_client.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_returns_err_after_max_retries(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock, capsys
    ) -> None:
        """Rejected values are not exposed in extraction errors or logs."""
        # Arrange
        secret = "INSTRUCTOR_VALIDATION_SECRET_SENTINEL"
        invalid_json = f'{{"name": "{secret}"}}'  # Missing age
        completion = Completion(content=invalid_json, model="gpt-4")
        mock_llm_client.complete.return_value = Ok(completion)

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ExtractionMaxRetriesError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
        assert mock_llm_client.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_extract_builds_correct_messages(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract builds correct message list."""
        # Arrange
        valid_json = '{"name": "Alice", "age": 35}'
        completion = Completion(content=valid_json, model="gpt-4")
        mock_llm_client.complete.return_value = Ok(completion)

        context = [
            ChatMessage(role=Role.SYSTEM, content="You are a helpful assistant"),
        ]

        # Act
        result = await extractor.extract(
            prompt="Extract user from: Alice is 35",
            response_model=UserInfo,
            context=context,
        )

        # Assert
        assert result.is_ok()

        # Verify the messages passed to the client
        call_args = mock_llm_client.complete.call_args
        messages = call_args[0][0]

        assert len(messages) == 2
        assert messages[0].role == Role.SYSTEM
        assert messages[0].content == "You are a helpful assistant"
        assert messages[1].role == Role.USER
        assert messages[1].content == "Extract user from: Alice is 35"

    @pytest.mark.asyncio
    async def test_extract_handles_llm_error(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock, capsys
    ) -> None:
        """LLM exception text is not exposed in extraction errors or logs."""
        # Arrange
        secret = "INSTRUCTOR_LLM_ERROR_SECRET_SENTINEL"
        llm_error = LLMError(secret)
        mock_llm_client.complete.return_value = Err(llm_error)

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ExtractionMaxRetriesError)
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err
        assert mock_llm_client.complete.call_count == 3

    @pytest.mark.asyncio
    async def test_extract_recovers_from_parse_error(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract recovers from parse error on retry."""
        # Arrange
        invalid_completion = Completion(content="not json", model="gpt-4")
        valid_completion = Completion(
            content='{"name": "Bob", "age": 40}', model="gpt-4"
        )

        mock_llm_client.complete.side_effect = [
            Ok(invalid_completion),
            Ok(valid_completion),
        ]

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
        )

        # Assert
        assert result.is_ok()
        user = result.unwrap()
        assert user.name == "Bob"
        assert user.age == 40

    @pytest.mark.asyncio
    async def test_extract_passes_kwargs_to_llm_client(
        self, extractor: InstructorExtractor, mock_llm_client: MagicMock
    ) -> None:
        """Test extract passes additional kwargs to llm_client.complete()."""
        # Arrange
        valid_json = '{"name": "Charlie", "age": 45}'
        completion = Completion(content=valid_json, model="gpt-4")
        mock_llm_client.complete.return_value = Ok(completion)

        # Act
        result = await extractor.extract(
            prompt="Extract user info",
            response_model=UserInfo,
            temperature=0.7,
            max_tokens=100,
        )

        # Assert
        assert result.is_ok()

        # Verify kwargs were passed through
        call_kwargs = mock_llm_client.complete.call_args[1]
        assert call_kwargs.get("temperature") == 0.7
        assert call_kwargs.get("max_tokens") == 100
