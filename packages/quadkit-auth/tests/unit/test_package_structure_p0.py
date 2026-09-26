"""Structural compliance tests for missing auth package markers."""

from __future__ import annotations


def test_mfa_package_import_surface() -> None:
    """Expose MFAManager from the mfa package marker."""
    from quadkit.auth.mfa import MFAManager

    assert MFAManager.__name__ == "MFAManager"


def test_policies_package_import_surface() -> None:
    """Expose the policies surface from the package marker."""
    from quadkit.auth.policies import (
        AuthorizationDecision,
        AuthorizationRequest,
        Condition,
        ConditionEvaluator,
        DecisionOutcome,
        InMemoryPolicyStore,
        OperatorRegistry,
        Policy,
        PolicyEffect,
        PolicyEngine,
        PolicyStoreProtocol,
    )

    assert AuthorizationDecision.__name__ == "AuthorizationDecision"
    assert AuthorizationRequest.__name__ == "AuthorizationRequest"
    assert PolicyEngine.__name__ == "PolicyEngine"
    assert Condition.__name__ == "Condition"
    assert Policy.__name__ == "Policy"
    assert PolicyEffect.ALLOW.value == "allow"
    assert ConditionEvaluator.__name__ == "ConditionEvaluator"
    assert DecisionOutcome.ALLOW.value == "allow"
    assert InMemoryPolicyStore.__name__ == "InMemoryPolicyStore"
    assert OperatorRegistry.__name__ == "OperatorRegistry"
    assert PolicyStoreProtocol.__name__ == "PolicyStoreProtocol"
