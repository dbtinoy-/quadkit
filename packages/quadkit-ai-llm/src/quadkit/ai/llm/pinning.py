"""Model revision pinning and policy enforcement (LXF-003)."""

from __future__ import annotations

from enum import StrEnum

from quadkit.ai.llm.exceptions import ModelRevisionMismatchError

__all__ = [
    "ModelPinPolicy",
    "enforce_pin_policy",
]


class ModelPinPolicy(StrEnum):
    """Policy for pinning LLM model revisions.

    Controls how strictly the configured ``model_revision`` is enforced
    against the revision returned by the provider.
    """

    EXACT = "exact"
    """Reject any response where the provider's revision does not exactly
    match the configured revision."""

    LATEST_MINOR = "latest_minor"
    """Accept any revision within the same major prefix (everything before
    the last ``-``). Use when minor patch updates are safe."""

    LATEST = "latest"
    """Accept any revision. The provider always returns the latest available
    revision (default — reproduces current behavior)."""


def enforce_pin_policy(
    expected_revision: str | None,
    actual_revision: str,
    policy: ModelPinPolicy,
) -> None:
    """Enforce a model pin policy.

    Args:
        expected_revision: The configured pinned revision, or ``None``.
        actual_revision: The revision returned by the provider.
        policy: The pin policy to enforce.

    Raises:
        ModelRevisionMismatchError: When the policy is violated.
    """
    if policy == ModelPinPolicy.LATEST:
        return

    if expected_revision is None:
        return

    if policy == ModelPinPolicy.EXACT:
        if expected_revision != actual_revision:
            raise ModelRevisionMismatchError(
                f"Model revision mismatch (EXACT): expected {expected_revision!r}, "
                f"got {actual_revision!r}"
            )

    if policy == ModelPinPolicy.LATEST_MINOR:
        major_expected = (
            expected_revision.rsplit("-", 1)[0]
            if "-" in expected_revision
            else expected_revision
        )
        major_actual = (
            actual_revision.rsplit("-", 1)[0]
            if "-" in actual_revision
            else actual_revision
        )
        if major_expected != major_actual:
            raise ModelRevisionMismatchError(
                f"Model revision mismatch (LATEST_MINOR): expected major {major_expected!r}, "
                f"got {major_actual!r}"
            )
