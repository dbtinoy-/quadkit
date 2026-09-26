"""Validation middleware for CQRS buses.

Provides message validation before handler execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.events.exceptions import ValidationError as CQRSValidationError
from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler

if TYPE_CHECKING:
    from collections.abc import Callable


class ValidationMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that validates messages before handling.

    Supports:
    - Pydantic model validation
    - Custom validators per message type
    - Global validators

    Example:
        ```python
        validator = ValidationMiddleware()

        # Add custom validator for specific command
        @validator.add_validator(CreateOrderCommand)
        async def validate_order(command: CreateOrderCommand):
            if not command.items:
                raise ValueError("Order must have at least one item")

        bus.use(validator)
        ```
    """

    def __init__(self, validate_pydantic: bool = True, strict_mode: bool = False):
        """Initialize the validation middleware.

        Args:
            validate_pydantic: Whether to run Pydantic validation
            strict_mode: Whether to fail on any validation error
        """
        self._validate_pydantic = validate_pydantic
        self._strict_mode = strict_mode
        self._validators: dict[type[Message], list[Callable]] = {}
        self._global_validators: list[Callable] = []

    def add_validator(self, message_type: type[Message] | None = None) -> Callable:
        """Decorator to add a validator for a message type.

        Args:
            message_type: Message type to validate (None for global)

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            if message_type is None:
                self._global_validators.append(func)
            else:
                if message_type not in self._validators:
                    self._validators[message_type] = []
                self._validators[message_type].append(func)
            return func

        return decorator

    def register_validator(
        self,
        message_type: type[Message],
        validator: Callable,
    ) -> None:
        """Register a validator function.

        Args:
            message_type: Message type to validate
            validator: Validator function
        """
        if message_type not in self._validators:
            self._validators[message_type] = []
        self._validators[message_type].append(validator)

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with validation."""
        errors: list[str] = []

        # Run Pydantic validation
        if self._validate_pydantic:
            try:
                # Re-validate the model
                message.model_validate(message.model_dump())  # type: ignore[attr-defined]
            except ValidationError as e:
                errors.extend([str(err) for err in e.errors()])  # type: ignore[operator]

        # Run global validators
        for validator in self._global_validators:
            try:
                result = validator(message)
                if hasattr(result, "__await__"):
                    await result
            except (ValueError, TypeError, AttributeError, RuntimeError) as e:
                errors.append(str(e))

        # Run type-specific validators
        message_type = type(message)
        for msg_type, validators in self._validators.items():
            if isinstance(message, msg_type):
                for validator in validators:
                    try:
                        result = validator(message)
                        if hasattr(result, "__await__"):
                            await result
                    except (ValueError, TypeError, AttributeError, RuntimeError) as e:
                        errors.append(str(e))

        # Handle validation errors
        if errors and (self._strict_mode or len(errors) > 0):
            raise CQRSValidationError(
                message=f"Validation failed for {message_type.__name__}",
                errors=errors,  # type: ignore[arg-type]
            )

        return await next_handler(message)


__all__ = ["ValidationMiddleware"]
