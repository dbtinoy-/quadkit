"""Secret rotation policy contract types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecretRotationPolicy:
    """Policy governing when a named secret should be rotated.

    Attributes:
        max_age_days: Maximum permitted age of the secret in days.
        rotation_warning_days: Number of days *before* ``max_age_days``
            at which an advance warning is emitted.
        auto_rotate: When ``True``, rotation is attempted automatically;
            otherwise only a warning is emitted.
    """

    max_age_days: int = 90
    rotation_warning_days: int = 14
    auto_rotate: bool = False
    _secret_name: str = field(default="", init=False, repr=False, compare=False)

    def is_warning_due(self, current_age_days: float) -> bool:
        """Return True if a rotation warning should be emitted.

        Args:
            current_age_days: Current age of the secret in fractional days.

        Returns:
            ``True`` when the warning threshold has been reached.
        """
        threshold = self.max_age_days - self.rotation_warning_days
        return current_age_days >= threshold

    def is_expired(self, current_age_days: float) -> bool:
        """Return True if the secret has exceeded its maximum permitted age.

        Args:
            current_age_days: Current age of the secret in fractional days.

        Returns:
            ``True`` when ``current_age_days >= max_age_days``.
        """
        return current_age_days >= self.max_age_days


__all__ = ["SecretRotationPolicy"]
