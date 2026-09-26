#!/usr/bin/env python3
"""Simple test script to verify basic auth functionality"""

import os
import sys

import pytest
from pydantic import SecretStr

from quadkit.logging import get_logger

# Add the src directory to the path

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_basic_functionality():
    """Test basic authentication functionality"""
    try:
        from quadkit.auth import JWTTokenManager, PasswordHasher, User

        logger.info("Imports successful")

        # Test password hashing
        password = "testpassword123"
        hashed = await PasswordHasher().hash(password)
        assert await PasswordHasher().verify(password, hashed)
        logger.info("Password hashing works")

        # Test JWT token manager
        manager = JWTTokenManager(SecretStr("test_secret_key_at_least_32_bytes_long"))
        user = User(
            user_id="test123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )

        token_obj = manager.create_token_pair(user)
        result = await manager.verify_token(token_obj.token)
        assert result is not None
        assert result.is_ok()
        assert result.unwrap().user_id == user.user_id
        logger.info("JWT tokens work")

        # Test user model
        user = user.with_role("admin")
        assert user.has_role("admin")
        assert user.has_role("user")  # Should still have the original role
        logger.info("User model works")

        logger.info("All basic functionality tests passed!")
        return True

    except (ImportError, AssertionError, RuntimeError, ValueError) as e:
        logger.error("Test failed: %s", e)
        import traceback

        traceback.print_exc()
        return False
