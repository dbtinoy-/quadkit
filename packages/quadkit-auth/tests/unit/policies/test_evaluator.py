
"""Unit tests for ConditionEvaluator and OperatorRegistry."""

import pytest
from typing import Protocol
from quadkit.auth.policies.evaluator import ConditionEvaluator, OperatorRegistry
from quadkit.auth.policies.types import Condition

class TestOperatorRegistry:
    def test_default_operators(self):
        registry = OperatorRegistry.with_defaults()
        assert registry.compare("value", "equals", "value") is True
        assert registry.compare("value", "equals", "other") is False
        assert registry.compare("value", "not_equals", "other") is True
        assert registry.compare("value", "contains", "val") is True
        assert registry.compare("value", "in", ["value", "other"]) is True
        assert registry.compare("123", "matches", r"\d+") is True
        assert registry.compare(10, "greater_than", 5) is True
        assert registry.compare(5, "less_than", 10) is True

    def test_unknown_operator(self):
        registry = OperatorRegistry.with_defaults()
        assert registry.compare("value", "unknown_op", "value") is False

class TestConditionEvaluator:
    def test_evaluate_simple(self):
        evaluator = ConditionEvaluator()
        condition = Condition(attribute="user.role", operator="equals", value="admin")
        context = {"user": {"role": "admin"}}
        assert evaluator.evaluate(condition, context) is True

    def test_evaluate_variable_substitution(self):
        evaluator = ConditionEvaluator()
        condition = Condition(attribute="resource.owner_id", operator="equals", value="${user.id}")
        context = {
            "user": {"id": "123"},
            "resource": {"owner_id": "123"}
        }
        assert evaluator.evaluate(condition, context) is True
