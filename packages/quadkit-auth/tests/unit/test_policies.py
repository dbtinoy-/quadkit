import pytest
from quadkit.auth.policies.engine import PolicyEngine
from quadkit.auth.policies.types import (
    Policy, PolicyEffect, AuthorizationRequest, DecisionOutcome, Condition
)

@pytest.fixture
def policy_engine():
    policies = [
        Policy(
            policy_id="p1",
            name="Allow Read",
            actions=["read"],
            resources=["item:*"],
            effect=PolicyEffect.ALLOW,
            priority=10
        ),
        Policy(
            policy_id="p2",
            name="Deny Delete",
            actions=["delete"],
            resources=["item:protected"],
            effect=PolicyEffect.DENY,
            priority=20
        ),
        Policy(
            policy_id="p3",
            name="Owner Only",
            actions=["write"],
            resources=["item:*"],
            effect=PolicyEffect.ALLOW,
            conditions=[
                Condition(attribute="user.id", operator="equals", value="${resource.owner_id}")
            ]
        )
    ]
    return PolicyEngine(policies)

def test_policy_engine_simple_allow(policy_engine):
    req = AuthorizationRequest(
        action="read",
        resource="item:123",
        principal="user1"
    )
    decision = policy_engine.evaluate(req)
    assert decision.decision == DecisionOutcome.ALLOW

def test_policy_engine_deny_override(policy_engine):
    # Matches both p1 (allow) and p2 (deny), p2 is higher priority and DENY
    req = AuthorizationRequest(
        action="delete",
        resource="item:protected",
        principal="user1"
    )
    decision = policy_engine.evaluate(req)
    assert decision.decision == DecisionOutcome.DENY

def test_policy_engine_abac_conditions(policy_engine):
    # Matches p3, needs condition check
    req = AuthorizationRequest(
        action="write",
        resource="item:123",
        principal="user1",
        context={
            "user": {"id": "user1"},
            "resource": {"owner_id": "user1"}
        }
    )
    decision = policy_engine.evaluate(req)
    assert decision.decision == DecisionOutcome.ALLOW
    
    req_fail = AuthorizationRequest(
        action="write",
        resource="item:123",
        principal="user2",
        context={
            "user": {"id": "user2"},
            "resource": {"owner_id": "user1"}
        }
    )
    decision = policy_engine.evaluate(req_fail)
    assert decision.decision == DecisionOutcome.INDETERMINATE

def test_pattern_match(policy_engine):
    assert policy_engine._pattern_match(["item:*"], "item:123")
    assert policy_engine._pattern_match(["*"], "anything")
    assert not policy_engine._pattern_match(["item:abc"], "item:123")
