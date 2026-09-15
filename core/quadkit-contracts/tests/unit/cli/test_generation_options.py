"""Tests for generation options, collision policy, and result manifests."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.contracts.cli.generators import (
    CollisionPolicy,
    GenerationOptions,
    GenerationResult,
    resolve_options,
)
from quadkit.contracts.exceptions.infra import CollidingFileError, InfrastructureError


class TestCollisionPolicy:
    def test_is_string_enum_with_expected_values(self) -> None:
        assert CollisionPolicy.SKIP == "skip"
        assert CollisionPolicy.OVERWRITE == "overwrite"
        assert CollisionPolicy.FAIL == "fail"

    def test_members_compare_equal_to_their_string_value(self) -> None:
        for member in CollisionPolicy:
            assert member == member.value


class TestGenerationOptions:
    def test_defaults_resolve_to_skip_without_dry_run(self) -> None:
        options = GenerationOptions()
        assert options.dry_run is False
        assert options.quiet is False
        assert options.policy is CollisionPolicy.SKIP

    def test_policy_is_never_none_after_construction(self) -> None:
        assert GenerationOptions(policy=None).policy is CollisionPolicy.SKIP
        assert GenerationOptions(force=True).policy is CollisionPolicy.OVERWRITE

    def test_frozen(self) -> None:
        import dataclasses

        options = GenerationOptions()
        with pytest.raises(dataclasses.FrozenInstanceError):
            options.dry_run = True  # type: ignore[misc]


class TestResolveOptions:
    def test_default_resolves_to_skip(self) -> None:
        resolved = resolve_options()
        assert resolved.policy is CollisionPolicy.SKIP
        assert resolved.dry_run is False

    def test_force_becomes_overwrite_when_no_explicit_policy(self) -> None:
        resolved = resolve_options(force=True)
        assert resolved.policy is CollisionPolicy.OVERWRITE

    @pytest.mark.parametrize("policy", list(CollisionPolicy))
    def test_explicit_policy_beats_force(self, policy: CollisionPolicy) -> None:
        resolved = resolve_options(force=True, policy=policy)
        assert resolved.policy is policy

    def test_dry_run_is_orthogonal_to_policy(self) -> None:
        resolved = resolve_options(dry_run=True, force=True)
        assert resolved.dry_run is True
        assert resolved.policy is CollisionPolicy.OVERWRITE

    def test_quiet_passes_through(self) -> None:
        assert resolve_options(quiet=True).quiet is True


class TestGenerationResultManifest:
    def test_manifest_maps_paths_to_actions(self) -> None:
        result = GenerationResult(
            files_created=[Path("a.py")],
            files_skipped=[Path("b.py")],
            files_overwritten=[Path("c.py")],
        )
        assert result.to_manifest() == {
            "a.py": "created",
            "b.py": "skipped",
            "c.py": "overwritten",
        }

    def test_empty_result_yields_empty_manifest(self) -> None:
        assert GenerationResult().to_manifest() == {}


class TestCollidingFileError:
    def test_is_infrastructure_error_leaf(self) -> None:
        error = CollidingFileError("user.py already exists")
        assert isinstance(error, InfrastructureError)
