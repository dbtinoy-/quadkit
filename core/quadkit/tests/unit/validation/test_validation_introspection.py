"""Tests for validation/introspection module."""
import pytest
from dataclasses import dataclass

from quadkit.validation import Field
from quadkit.validation.schema import field_validator, model_validator
from quadkit.validation.schema import (
    collect_field_validators,
    collect_model_validators,
)


class IntrospectionTestModel:
    """Test model for introspection."""
    def __init__(self, name: str = "", age: int = 0) -> None:
        self.name = name
        self.age = age


class TestCollectFieldValidators:
    """Tests for collect_field_validators function."""

    def test_collect_no_validators(self) -> None:
        """Test collecting from class with no validators."""
        validators = collect_field_validators(IntrospectionTestModel)
        assert validators == {}

    def test_collect_single_validator(self) -> None:
        """Test collecting single field validator."""

        @dataclass
        class ModelWithValidator(IntrospectionTestModel):
            @field_validator("name")
            @classmethod
            def validate_name(cls, v: str) -> str:
                return v

        validators = collect_field_validators(ModelWithValidator)
        assert "name" in validators
        assert len(validators["name"]) == 1

    def test_collect_multiple_validators(self) -> None:
        """Test collecting multiple field validators."""

        @dataclass
        class ModelWithMultiple(IntrospectionTestModel):
            @field_validator("name")
            @classmethod
            def validate_name(cls, v: str) -> str:
                return v

            @field_validator("name")
            @classmethod
            def validate_name_2(cls, v: str) -> str:
                return v.upper()

        validators = collect_field_validators(ModelWithMultiple)
        assert "name" in validators
        assert len(validators["name"]) == 2

    def test_collect_validators_sorted(self) -> None:
        """Test that validators are sorted by mode (before first)."""

        @dataclass
        class ModelWithModes(IntrospectionTestModel):
            @field_validator("name", mode="after")
            @classmethod
            def after_validator(cls, v: str) -> str:
                return v

            @field_validator("name", mode="before")
            @classmethod
            def before_validator(cls, v: str) -> str:
                return v

        validators = collect_field_validators(ModelWithModes)
        assert validators["name"][0][0] == "before"
        assert validators["name"][1][0] == "after"

    def test_collect_inherited_validators(self) -> None:
        """Test that inherited validators are collected."""

        @dataclass
        class Parent(IntrospectionTestModel):
            @field_validator("name")
            @classmethod
            def validate_name(cls, v: str) -> str:
                return v

        @dataclass
        class Child(Parent):
            pass

        validators = collect_field_validators(Child)
        assert "name" in validators


class TestCollectModelValidators:
    """Tests for collect_model_validators function."""

    def test_collect_no_model_validators(self) -> None:
        """Test collecting from class with no model validators."""
        validators = collect_model_validators(IntrospectionTestModel)
        assert validators == {"before": [], "after": [], "wrap": []}

    def test_collect_returns_all_modes(self) -> None:
        """Test that collect returns all three mode keys."""
        validators = collect_model_validators(IntrospectionTestModel)
        assert "before" in validators
        assert "after" in validators
        assert "wrap" in validators