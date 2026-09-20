"""Validation pipe for Pydantic model validation.

Validates incoming data against Pydantic models.
"""

from __future__ import annotations

from typing import Any

from quadkit.web.protocols import ParamMetadata, PipeProtocol


class ValidationPipe(PipeProtocol):
    """PipeProtocol that validates data against Pydantic models.

    Uses Pydantic's model_validate() for validation.

    Example:
        ```python
        from quadkit.domain import DomainModel

        @dataclass(init=False)
        class CreateUserRequest(DomainModel):
            name: str
            email: str

        class UserController(Controller):
            @post("/users")
            async def create_user(self, @body(pipe=ValidationPipe()) data: CreateUserRequest):
                ...
        ```
    """

    def __init__(self, model: type | None = None):
        """Initialize the validation pipe.

        Args:
            model: Optional Pydantic model class to validate against.
        """
        self._model = model

    async def transform(self, value: Any, metadata: ParamMetadata) -> Any:
        """Validate the value against the Pydantic model.

        Args:
            value: The value to validate.
            metadata: Metadata about the parameter.

        Returns:
            Validated model instance.

        Raises:
            ValidationError: If validation fails.
        """
        from quadkit.contracts.exceptions.domain import ValidationError

        if value is None:
            return None

        # Use provided model or try to infer from metadata
        model = self._model

        if model is None:
            # Try to get expected type from metadata
            expected_type = metadata.expected_type
            if expected_type and hasattr(expected_type, "model_validate"):
                model = expected_type

        if model is None:
            # No model to validate against
            return value

        try:
            if hasattr(model, "model_validate"):
                # Pydantic v2
                return model.model_validate(value)
            if hasattr(model, "parse_obj"):
                # Pydantic v1
                return model.parse_obj(value)
            # Not a Pydantic model
            return value
        except Exception as e:  # noqa: BLE001 — duck-typing on Pydantic ValidationError (v1/v2) requires catching broadly before re-raising
            from quadkit.contracts.exceptions.domain import (
                ValidationError as QuadkitValidationError,
            )

            if isinstance(e, QuadkitValidationError):
                raise

            # Check if it's a Pydantic ValidationError
            if type(e).__name__ == "ValidationError":
                from quadkit.contracts.exceptions.domain import FieldError

                qk_errors = []
                # Extract errors from pydantic (works for v1 and v2)
                pydantic_errors = getattr(e, "errors", None)
                if callable(pydantic_errors):
                    pydantic_errors = pydantic_errors()
                elif pydantic_errors is None:
                    pydantic_errors = []

                for err in pydantic_errors:
                    # For a single parameter pipe, the field name is usually the parameter name
                    # but we can try to get it from location
                    loc = err.get("loc", [])
                    field = (
                        ".".join(str(part) for part in loc) if loc else metadata.name
                    )

                    qk_errors.append(
                        FieldError(
                            field=field,
                            message=err.get("msg", "Invalid value"),
                            code=err.get("type", "invalid"),
                        )
                    )
                raise ValidationError(
                    f"Validation failed for {metadata.name}", errors=qk_errors
                ) from e
            raise


__all__ = ["ValidationPipe"]
