"""Unit tests for quadkit.contracts.feature_flags models."""

from __future__ import annotations

import pytest

from quadkit.contracts.feature_flags import (
    FlagEvaluation,
    FlagType,
    FlagValue,
)


class TestFlagType:
    """Tests for FlagType enum."""

    def test_boolean_value(self) -> None:
        """Verify BOOLEAN flag type value."""
        assert FlagType.BOOLEAN.value == "boolean"

    def test_percentage_value(self) -> None:
        """Verify PERCENTAGE flag type value."""
        assert FlagType.PERCENTAGE.value == "percentage"

    def test_user_list_value(self) -> None:
        """Verify USER_LIST flag type value."""
        assert FlagType.USER_LIST.value == "user_list"

    def test_user_attribute_value(self) -> None:
        """Verify USER_ATTRIBUTE flag type value."""
        assert FlagType.USER_ATTRIBUTE.value == "user_attribute"

    def test_time_based_value(self) -> None:
        """Verify TIME_BASED flag type value."""
        assert FlagType.TIME_BASED.value == "time_based"

    def test_variant_value(self) -> None:
        """Verify VARIANT flag type value."""
        assert FlagType.VARIANT.value == "variant"

    def test_all_types_defined(self) -> None:
        """Verify all flag types are defined."""
        types = list(FlagType)
        assert len(types) == 7
        assert FlagType.BOOLEAN in types
        assert FlagType.PERCENTAGE in types
        assert FlagType.USER_LIST in types
        assert FlagType.USER_ATTRIBUTE in types
        assert FlagType.TENANT_LIST in types
        assert FlagType.TIME_BASED in types
        assert FlagType.VARIANT in types


class TestFlagValue:
    """Tests for FlagValue type alias."""

    def test_flag_value_is_bool(self) -> None:
        """Verify FlagValue accepts boolean."""
        value: FlagValue = True
        assert value is True

    def test_flag_value_is_str(self) -> None:
        """Verify FlagValue accepts string."""
        value: FlagValue = "variant-a"
        assert value == "variant-a"

    def test_flag_value_is_float(self) -> None:
        """Verify FlagValue accepts float."""
        value: FlagValue = 0.5
        assert value == 0.5


class TestFlagEvaluation:
    """Tests for FlagEvaluation dataclass."""

    def test_create_basic_evaluation(self) -> None:
        """Verify basic FlagEvaluation creation."""
        evaluation = FlagEvaluation(
            key="my-flag",
            value=True,
        )
        assert evaluation.key == "my-flag"
        assert evaluation.value is True
        assert evaluation.flag_type == FlagType.BOOLEAN
        assert evaluation.reason == "DEFAULT"
        assert evaluation.variant is None

    def test_create_with_all_fields(self) -> None:
        """Verify FlagEvaluation with all fields."""
        evaluation = FlagEvaluation(
            key="variant-flag",
            value="variant-b",
            flag_type=FlagType.VARIANT,
            reason="TARGETING",
            variant="variant-b",
            metadata={"variant_config": {"B": {"weight": 50}}},
        )
        assert evaluation.key == "variant-flag"
        assert evaluation.value == "variant-b"
        assert evaluation.flag_type == FlagType.VARIANT
        assert evaluation.reason == "TARGETING"
        assert evaluation.variant == "variant-b"
        assert evaluation.metadata == {"variant_config": {"B": {"weight": 50}}}

    def test_create_percentage_evaluation(self) -> None:
        """Verify percentage flag evaluation."""
        evaluation = FlagEvaluation(
            key="rollout",
            value=0.25,
            flag_type=FlagType.PERCENTAGE,
            reason="TARGETING",
        )
        assert evaluation.value == 0.25
        assert evaluation.flag_type == FlagType.PERCENTAGE

    def test_default_metadata_empty(self) -> None:
        """Verify default metadata is empty dict."""
        evaluation = FlagEvaluation(key="test", value=True)
        assert evaluation.metadata == {}

    def test_is_frozen(self) -> None:
        """Verify FlagEvaluation is frozen (immutable)."""
        evaluation = FlagEvaluation(key="test", value=True)
        with pytest.raises(AttributeError):
            evaluation.value = False  # type: ignore[assignment]

    def test_equality(self) -> None:
        """Verify FlagEvaluation equality."""
        eval1 = FlagEvaluation(key="test", value=True)
        eval2 = FlagEvaluation(key="test", value=True)
        assert eval1 == eval2

    def test_inequality(self) -> None:
        """Verify FlagEvaluation inequality."""
        eval1 = FlagEvaluation(key="test", value=True)
        eval2 = FlagEvaluation(key="test", value=False)
        assert eval1 != eval2