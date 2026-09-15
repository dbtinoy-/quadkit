"""Tests for skills contracts."""

import pytest
from unittest.mock import MagicMock

from quadkit.contracts.ai.exceptions import AIError
from quadkit.contracts.ai.skills import (
    SkillDefinition,
    SkillError,
    SkillExecutorProtocol,
    SkillParameter,
    SkillProtocol,
    SkillRegistryProtocol,
    SkillResult,
)


class TestSkillDataclasses:
    """Test skill dataclass definitions."""

    def test_skill_parameter_frozen(self) -> None:
        """SkillParameter should be frozen."""
        param = SkillParameter(name="count", type="integer", description="How many")
        with pytest.raises(AttributeError):
            param.required = False

    def test_skill_parameter_defaults(self) -> None:
        """SkillParameter should have sensible defaults."""
        param = SkillParameter(name="count", type="integer", description="How many")
        assert param.required is True
        assert param.default is None
        assert param.enum is None
        assert param.min_value is None
        assert param.max_value is None
        assert param.max_length is None

    def test_skill_definition_frozen(self) -> None:
        """SkillDefinition should be frozen."""
        defn = SkillDefinition(name="test", description="Test skill")
        with pytest.raises(AttributeError):
            defn.cacheable = True

    def test_skill_definition_defaults(self) -> None:
        """SkillDefinition should have sensible defaults."""
        defn = SkillDefinition(name="test", description="Test skill")
        assert defn.category == "general"
        assert defn.requires_confirmation is False
        assert defn.cacheable is False
        assert defn.max_retries == 0
        assert defn.timeout_seconds == 30.0
        assert defn.parameters_schema == {}
        assert defn.returns_schema == {}
        assert defn.permissions == []

    def test_skill_result_frozen(self) -> None:
        """SkillResult should be frozen."""
        result = SkillResult(skill_name="test", success=True, output="value")
        with pytest.raises(AttributeError):
            result.success = False

    def test_skill_result_defaults(self) -> None:
        """SkillResult should have sensible defaults."""
        result = SkillResult(skill_name="test", success=True)
        assert result.output is None
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.cached is False
        assert result.metadata == {}

    def test_skill_error_exception(self) -> None:
        """SkillError should be an AIError subclass."""
        error = SkillError("test error")
        assert isinstance(error, Exception)
        assert isinstance(error, AIError)
        assert "test error" in str(error)


class TestSkillProtocols:
    """Test skill protocols are runtime checkable."""

    def test_skill_protocol_runtime_checkable(self) -> None:
        """SkillProtocol should be runtime checkable."""
        assert isinstance(SkillProtocol, type)

        defn = SkillDefinition(name="test", description="Test skill")

        class MockSkill:
            @property
            def definition(self):
                return defn

            async def execute(self, **kwargs):
                result = SkillResult(skill_name="test", success=True)
                return MagicMock()

            def validate(self, params):
                return []

        mock = MockSkill()
        assert isinstance(mock, SkillProtocol)

    def test_skill_registry_protocol_runtime_checkable(self) -> None:
        """SkillRegistryProtocol should be runtime checkable."""
        assert isinstance(SkillRegistryProtocol, type)

        class MockRegistry:
            def register(self, skill):
                pass

            def get(self, name):
                return None

            def list_skills(self, category=None, permissions=None):
                return []

            def get_schemas(self):
                return []

        mock = MockRegistry()
        assert isinstance(mock, SkillRegistryProtocol)

    def test_skill_executor_protocol_runtime_checkable(self) -> None:
        """SkillExecutorProtocol should be runtime checkable."""
        assert isinstance(SkillExecutorProtocol, type)

        class MockExecutor:
            async def execute(self, skill_name, params, user_id=None, session_id=None):
                result = SkillResult(skill_name=skill_name, success=True)
                return MagicMock()

        mock = MockExecutor()
        assert isinstance(mock, SkillExecutorProtocol)
