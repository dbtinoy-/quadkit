"""Tests for GraphQL context contracts.

Tests the GraphQLPrincipal dataclass and GraphQLPrincipalResolverProtocol
that enable shared principal resolution across the framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from quadkit.contracts.graphql.types import GraphQLPrincipal


class TestGraphQLPrincipal:
    """Test suite for GraphQLPrincipal dataclass."""

    def test_graphql_principal_is_frozen_dataclass(self) -> None:
        """GraphQLPrincipal must be a frozen dataclass."""
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        principal = GraphQLPrincipal()

        # Verify it's frozen by attempting mutation
        with pytest.raises(AttributeError):
            principal.internal_user_id = "some-id"  # type: ignore[misc]

    def test_graphql_principal_defaults_all_fields_to_none(self) -> None:
        """GraphQLPrincipal must default all fields to None."""
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        principal = GraphQLPrincipal()

        assert principal.internal_user_id is None
        assert principal.subject_id is None
        assert principal.email is None
        assert principal.raw_user is None

    def test_graphql_principal_accepts_all_field_values(self) -> None:
        """GraphQLPrincipal must accept values for all documented fields."""
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        raw_user_obj = {"id": "123", "name": "Test User"}

        principal = GraphQLPrincipal(
            internal_user_id="user-123",
            subject_id="sub-456",
            email="test@example.com",
            raw_user=raw_user_obj,
        )

        assert principal.internal_user_id == "user-123"
        assert principal.subject_id == "sub-456"
        assert principal.email == "test@example.com"
        assert principal.raw_user == raw_user_obj

    def test_graphql_principal_allows_partial_initialization(self) -> None:
        """GraphQLPrincipal must allow partial field initialization."""
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        principal = GraphQLPrincipal(
            internal_user_id="user-123",
            email="test@example.com",
        )

        assert principal.internal_user_id == "user-123"
        assert principal.subject_id is None
        assert principal.email == "test@example.com"
        assert principal.raw_user is None


class TestGraphQLPrincipalResolverProtocol:
    """Test suite for GraphQLPrincipalResolverProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """GraphQLPrincipalResolverProtocol must be runtime_checkable."""
        from quadkit.contracts.graphql.protocols import (
            GraphQLPrincipalResolverProtocol,
        )

        # Verify we can use isinstance() checks, which requires @runtime_checkable
        class ValidResolver:
            async def resolve_principal(self, user: Any, request: Any = None) -> Any:
                return None

        # If the protocol is runtime_checkable, isinstance works
        resolver = ValidResolver()
        assert isinstance(resolver, GraphQLPrincipalResolverProtocol)

    @pytest.mark.asyncio
    async def test_protocol_requires_resolve_principal_method(self) -> None:
        """GraphQLPrincipalResolverProtocol must require async resolve_principal method."""
        from quadkit.contracts.graphql.protocols import (
            GraphQLPrincipalResolverProtocol,
        )
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        # Implementation that satisfies the protocol
        class ValidResolver:
            async def resolve_principal(
                self, user: Any, request: Any = None
            ) -> GraphQLPrincipal:
                return GraphQLPrincipal(internal_user_id="test-user")

        resolver = ValidResolver()
        assert isinstance(resolver, GraphQLPrincipalResolverProtocol)

    @pytest.mark.asyncio
    async def test_protocol_rejects_missing_method(self) -> None:
        """GraphQLPrincipalResolverProtocol must reject classes without resolve_principal."""
        from quadkit.contracts.graphql.protocols import (
            GraphQLPrincipalResolverProtocol,
        )

        class InvalidResolver:
            pass

        resolver = InvalidResolver()
        assert not isinstance(resolver, GraphQLPrincipalResolverProtocol)

    @pytest.mark.asyncio
    async def test_protocol_validates_correct_signature(self) -> None:
        """GraphQLPrincipalResolverProtocol validates structural compatibility."""
        from quadkit.contracts.graphql.protocols import (
            GraphQLPrincipalResolverProtocol,
        )
        from quadkit.contracts.graphql.types import GraphQLPrincipal

        # Valid async implementation with correct signature
        class ValidResolver:
            async def resolve_principal(
                self, user: Any, request: Any = None
            ) -> GraphQLPrincipal:
                return GraphQLPrincipal(internal_user_id="test-user")

        # Wrong method name should fail
        class WrongMethodName:
            async def resolve_user(
                self, user: Any, request: Any = None
            ) -> GraphQLPrincipal:
                return GraphQLPrincipal()

        valid = ValidResolver()
        wrong_name = WrongMethodName()

        assert isinstance(valid, GraphQLPrincipalResolverProtocol)
        assert not isinstance(wrong_name, GraphQLPrincipalResolverProtocol)


class TestGraphQLContractsExports:
    """Test suite for GraphQL contracts module exports."""

    def test_graphql_principal_exported_from_graphql_module(self) -> None:
        """GraphQLPrincipal must be exported from quadkit.contracts.graphql."""
        from quadkit.contracts.graphql import GraphQLPrincipal

        # Should be importable from the package root
        assert GraphQLPrincipal is not None

    def test_graphql_principal_resolver_protocol_exported_from_graphql_module(
        self,
    ) -> None:
        """GraphQLPrincipalResolverProtocol must be exported from quadkit.contracts.graphql."""
        from quadkit.contracts.graphql import GraphQLPrincipalResolverProtocol

        # Should be importable from the package root
        assert GraphQLPrincipalResolverProtocol is not None

    def test_graphql_principal_in_all_export(self) -> None:
        """GraphQLPrincipal must be in __all__ of quadkit.contracts.graphql."""
        from quadkit.contracts import graphql

        assert "GraphQLPrincipal" in graphql.__all__

    def test_graphql_principal_resolver_protocol_in_all_export(self) -> None:
        """GraphQLPrincipalResolverProtocol must be in __all__."""
        from quadkit.contracts import graphql

        assert "GraphQLPrincipalResolverProtocol" in graphql.__all__
