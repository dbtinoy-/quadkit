"""Test domain error hierarchy for Result pattern."""

from __future__ import annotations

import pytest

from quadkit.contracts.ai.exceptions import (
    AIError,
    AIMemoryError,
    LLMError,
    RAGError,
    SkillError,
)
from quadkit.contracts.auth.exceptions import AuthError
from quadkit.contracts.infra.cache.exceptions import CacheError
from quadkit.contracts.data.exceptions import DataError
from quadkit.contracts.exceptions.domain import DomainError


def test_cache_error_hierarchy() -> None:
    """Verify CacheError extends DomainError."""
    assert issubclass(CacheError, DomainError)
    error = CacheError("test")
    assert isinstance(error, DomainError)


def test_auth_error_hierarchy() -> None:
    """Verify AuthError extends DomainError."""
    assert issubclass(AuthError, DomainError)
    error = AuthError("test")
    assert isinstance(error, DomainError)


def test_data_error_hierarchy() -> None:
    """Verify DataError extends DomainError."""
    assert issubclass(DataError, DomainError)
    error = DataError("test")
    assert isinstance(error, DomainError)


def test_ai_error_hierarchy() -> None:
    """Verify AIError extends DomainError."""
    assert issubclass(AIError, DomainError)
    error = AIError("test")
    assert isinstance(error, DomainError)


def test_llm_error_hierarchy() -> None:
    """Verify LLMError extends AIError."""
    assert issubclass(LLMError, AIError)
    assert issubclass(LLMError, DomainError)


def test_rag_error_hierarchy() -> None:
    """Verify RAGError extends AIError."""
    assert issubclass(RAGError, AIError)
    assert issubclass(RAGError, DomainError)


def test_memory_error_hierarchy() -> None:
    """Verify AIMemoryError extends AIError."""
    assert issubclass(AIMemoryError, AIError)
    assert issubclass(AIMemoryError, DomainError)


def test_skill_error_hierarchy() -> None:
    """Verify SkillError extends AIError."""
    assert issubclass(SkillError, AIError)
    assert issubclass(SkillError, DomainError)


def test_error_inheritance_chain() -> None:
    """Verify all domain errors share common parent."""
    domain_error_subclasses = [CacheError, AuthError, DataError, AIError]
    for error_cls in domain_error_subclasses:
        assert issubclass(error_cls, DomainError)
        error_instance = error_cls("test error")
        assert isinstance(error_instance, DomainError)
