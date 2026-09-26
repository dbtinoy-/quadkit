"""Schema models for event versioning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from quadkit.events.exceptions import EventError


class SchemaIncompatibleError(EventError):
    """Raised when a schema is not compatible with previous version."""

    _code: str = "QK_ERR_EVT_022"

    def __init__(
        self,
        message: str,
        event_type: str,
        version: int,
        issues: list[str] | None = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "event_type": event_type,
                "version": version,
                "issues": issues or [],
            },
        )
        self.event_type = event_type
        self.version = version
        self.issues = issues or []


class SchemaNotFoundError(EventError):
    """Raised when a schema is not found."""

    _code: str = "QK_ERR_EVT_023"

    def __init__(self, event_type: str, version: int | None = None) -> None:
        message = f"Schema not found: {event_type}"
        if version:
            message += f" v{version}"
        super().__init__(
            message,
            details={"event_type": event_type, "version": version},
        )
        self.event_type = event_type
        self.version = version


@dataclass
class EventSchema:
    """Schema definition for an event type."""

    event_type: str
    version: int
    event_class: type | None = None
    json_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    deprecated: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_compatible_with(self, other: EventSchema) -> tuple[bool, list[str]]:
        """Check backward compatibility with another schema."""
        issues: list[str] = []

        if not self.json_schema or not other.json_schema:
            return True, []

        old_props = other.json_schema.get("properties", {})
        new_props = self.json_schema.get("properties", {})
        old_required = set(other.json_schema.get("required", []))
        new_required = set(self.json_schema.get("required", []))

        added_required = new_required - old_required
        if added_required:
            issues.append(f"New required fields added: {', '.join(added_required)}")

        removed_fields = set(old_props.keys()) - set(new_props.keys())
        if removed_fields:
            issues.append(f"Fields removed: {', '.join(removed_fields)}")

        for prop_name in old_props:
            if prop_name in new_props:
                old_type = old_props[prop_name].get("type")
                new_type = new_props[prop_name].get("type")
                if old_type and new_type and old_type != new_type:
                    issues.append(
                        f"Field '{prop_name}' type changed: {old_type} -> {new_type}",
                    )

        return len(issues) == 0, issues

    def validate(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate data against this schema."""
        errors: list[str] = []

        if not self.json_schema:
            return True, []

        required = self.json_schema.get("required", [])
        for field_name in required:
            if field_name not in data:
                errors.append(f"Missing required field: {field_name}")

        properties = self.json_schema.get("properties", {})
        for field_name, value in data.items():
            if field_name in properties:
                expected_type = properties[field_name].get("type")
                if expected_type:
                    if not self._check_type(value, expected_type):
                        errors.append(
                            f"Field '{field_name}' has wrong type: "
                            f"expected {expected_type}, got {type(value).__name__}",
                        )

        return len(errors) == 0, errors

    def _check_type(self, value: Any, expected: str) -> bool:
        """Check if value matches expected JSON Schema type."""
        type_map: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        expected_type = type_map.get(expected)
        return isinstance(value, expected_type) if expected_type is not None else True
