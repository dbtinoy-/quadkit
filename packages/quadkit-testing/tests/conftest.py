"""Test fixtures for quadkit-testing."""
import pytest

from quadkit.testing import TestEnvironment


@pytest.fixture
def test_env():
    """Create a clean test environment."""
    return TestEnvironment()