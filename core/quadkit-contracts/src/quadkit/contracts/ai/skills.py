"""Composable skills/tools system contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

from quadkit.contracts.ai.exceptions import SkillError

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result


@dataclass(frozen=True)
class SkillParameter:
    """Parameter definition for a skill.

    Attributes:
        name: Parameter name
        type: Parameter type (e.g., "string", "integer", "boolean")
        description: Human-readable description
        required: Whether this parameter is required
        default: Default value if not provided
        enum: List of allowed values (if restricted)
        min_value: Numeric minimum (if applicable)
        max_value: Numeric maximum (if applicable)
        max_length: String max length (if applicable)
    """

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None
    min_value: float | None = None
    max_value: float | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class SkillDefinition:
    """Definition of a skill's interface and behavior.

    Attributes:
        name: Unique skill name
        description: What the skill does
        parameters_schema: JSON Schema for parameters
        returns_schema: JSON Schema for return value
        category: Skill category for organization
        requires_confirmation: If True, requires user approval before execution
        cacheable: Whether results can be cached
        max_retries: Maximum retry attempts on failure
        timeout_seconds: Execution timeout in seconds
        permissions: Required permissions to execute
    """

    name: str
    description: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    returns_schema: dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    requires_confirmation: bool = False
    cacheable: bool = False
    max_retries: int = 0
    timeout_seconds: float = 30.0
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillResult:
    """Result of a skill execution.

    Attributes:
        skill_name: Name of the executed skill
        success: Whether execution succeeded
        output: The output value (if successful)
        error: Error message (if failed)
        duration_ms: Time taken to execute
        cached: Whether result came from cache
        metadata: Additional execution metadata
    """

    skill_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    cached: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SkillProtocol(Protocol):
    """Protocol for a composable skill.

    A skill is an async-callable capability that can be registered,
    discovered, and executed with validation and error handling.
    """

    @property
    def definition(self) -> SkillDefinition:
        """Get the skill definition.

        Returns:
            The skill's definition including parameters and metadata
        """
        ...

    async def execute(self, **kwargs: Any) -> Result[SkillResult, SkillError]:
        """Execute the skill.

        Args:
            **kwargs: Skill-specific parameters

        Returns:
            Result with SkillResult on success or SkillError on failure
        """
        ...

    def validate(self, params: dict[str, Any]) -> list[str]:
        """Validate parameters against the definition.

        Args:
            params: Parameters to validate

        Returns:
            List of validation errors (empty if valid)
        """
        ...


@runtime_checkable
class SkillRegistryProtocol(Protocol):
    """Protocol for registering and discovering skills.

    Maintains a registry of available skills with support for
    filtering by category and permissions.
    """

    def register(self, skill: SkillProtocol) -> None:
        """Register a skill in the registry.

        Args:
            skill: The skill to register
        """
        ...

    def get(self, name: str) -> SkillProtocol | None:
        """Get a skill by name.

        Args:
            name: The skill name

        Returns:
            The skill, or None if not found
        """
        ...

    def list_skills(
        self,
        category: str | None = None,
        permissions: list[str] | None = None,
    ) -> list[SkillDefinition]:
        """List available skills with optional filtering.

        Args:
            category: Filter by skill category
            permissions: Filter to skills that match any of these permissions

        Returns:
            List of skill definitions matching the criteria
        """
        ...

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI function-calling compatible schemas.

        Returns:
            List of skill schemas in OpenAI function calling format
        """
        ...


@runtime_checkable
class SkillExecutorProtocol(Protocol):
    """Protocol for executing skills with lifecycle management.

    Handles skill selection, validation, execution, retry, caching,
    permission checking, and observability.
    """

    async def execute(
        self,
        skill_name: str,
        params: dict[str, Any],
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> Result[SkillResult, SkillError]:
        """Execute a skill with full lifecycle management.

        Args:
            skill_name: Name of the skill to execute
            params: Parameters for the skill
            user_id: Optional user ID for permission checks
            session_id: Optional session ID for context

        Returns:
            Result with SkillResult on success or SkillError on failure
        """
        ...


@runtime_checkable
class ToolkitProtocol(Protocol):
    """Protocol for a collection of related skills.

    A toolkit groups semantically related skills together, such as
    database operations, web browsing, or file operations.
    """

    @property
    def tools(self) -> tuple[SkillProtocol, ...]:
        """Get the collection of skills in this toolkit.

        Returns:
            Tuple of SkillProtocol instances provided by this toolkit.
        """
        ...

    @property
    def name(self) -> str:
        """Get the toolkit name.

        Returns:
            Unique identifier for this toolkit.
        """
        ...

    @property
    def description(self) -> str:
        """Get the toolkit description.

        Returns:
            Human-readable description of what this toolkit provides.
        """
        ...


__all__ = [
    "SkillDefinition",
    "SkillError",
    "SkillExecutorProtocol",
    "SkillParameter",
    "SkillProtocol",
    "SkillRegistryProtocol",
    "SkillResult",
    "ToolkitProtocol",
]
