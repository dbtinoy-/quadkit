"""Tests for auth policies types."""

import pytest

from quadkit.auth.policies.types import (
    AuthorizationDecision,
    AuthorizationRequest,
    Condition,
    DecisionOutcome,
    Policy,
    PolicyEffect,
)


class TestPolicyEffect:
    """Tests for PolicyEffect enum."""

    def test_policy_effect_values(self) -> None:
        """Test PolicyEffect enum values."""
        assert PolicyEffect.ALLOW.value == "allow"
        assert PolicyEffect.DENY.value == "deny"

    def test_policy_effect_members(self) -> None:
        """Test PolicyEffect has expected members."""
        members = list(PolicyEffect)
        assert len(members) == 2


class TestDecisionOutcome:
    """Tests for DecisionOutcome enum."""

    def test_decision_outcome_values(self) -> None:
        """Test DecisionOutcome enum values."""
        assert DecisionOutcome.ALLOW.value == "allow"
        assert DecisionOutcome.DENY.value == "deny"
        assert DecisionOutcome.INDETERMINATE.value == "indeterminate"

    def test_decision_outcome_members(self) -> None:
        """Test DecisionOutcome has expected members."""
        members = list(DecisionOutcome)
        assert len(members) == 3


class TestCondition:
    """Tests for Condition dataclass."""

    def test_condition_creation(self) -> None:
        """Test Condition creation."""
        cond = Condition(attribute="role", operator="eq", value="admin")
        assert cond.attribute == "role"
        assert cond.operator == "eq"
        assert cond.value == "admin"

    def test_condition_immutable(self) -> None:
        """Test Condition is immutable (frozen dataclass)."""
        cond = Condition(attribute="role", operator="eq", value="admin")
        with pytest.raises(Exception):
            cond.attribute = "other"


class TestPolicy:
    """Tests for Policy dataclass."""

    def test_policy_defaults(self) -> None:
        """Test Policy default values."""
        policy = Policy(
            policy_id="policy1",
            name="Test Policy",
            effect=PolicyEffect.ALLOW,
        )
        assert policy.policy_id == "policy1"
        assert policy.name == "Test Policy"
        assert policy.effect == PolicyEffect.ALLOW
        assert policy.principals == []
        assert policy.actions == []
        assert policy.resources == []
        assert policy.priority == 0

    def test_policy_with_conditions(self) -> None:
        """Test Policy with conditions."""
        cond = Condition(attribute="role", operator="eq", value="admin")
        policy = Policy(
            policy_id="policy1",
            name="Test Policy",
            effect=PolicyEffect.ALLOW,
            conditions=[cond],
            priority=10,
        )
        assert len(policy.conditions) == 1
        assert policy.priority == 10


class TestAuthorizationRequest:
    """Tests for AuthorizationRequest dataclass."""

    def test_authorization_request_defaults(self) -> None:
        """Test AuthorizationRequest default values."""
        request = AuthorizationRequest(
            principal="user:123",
            action="read",
            resource="document:456",
        )
        assert request.principal == "user:123"
        assert request.action == "read"
        assert request.resource == "document:456"
        assert request.context == {}

    def test_authorization_request_with_context(self) -> None:
        """Test AuthorizationRequest with context."""
        request = AuthorizationRequest(
            principal="user:123",
            action="read",
            resource="document:456",
            context={"ip": "192.168.1.1"},
        )
        assert request.context == {"ip": "192.168.1.1"}


class TestAuthorizationDecision:
    """Tests for AuthorizationDecision dataclass."""

    def test_authorization_decision_allow(self) -> None:
        """Test AuthorizationDecision with allow."""
        decision = AuthorizationDecision(
            decision=DecisionOutcome.ALLOW,
            reason="User is admin",
            applied_policies=["policy1"],
        )
        assert decision.decision == DecisionOutcome.ALLOW
        assert decision.reason == "User is admin"
        assert decision.applied_policies == ["policy1"]

    def test_authorization_decision_deny(self) -> None:
        """Test AuthorizationDecision with deny."""
        decision = AuthorizationDecision(
            decision=DecisionOutcome.DENY,
            reason="User does not have permission",
        )
        assert decision.decision == DecisionOutcome.DENY
        assert decision.applied_policies == []
