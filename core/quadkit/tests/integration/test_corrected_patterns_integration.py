"""Integration tests for corrected user handling patterns"""

from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.primitives.context import Context


@pytest.mark.integration
class TestUserHandlingIntegration:
    """Integration tests for complete user handling flow"""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock user repository"""
        repo = Mock()
        repo.get_user_dto = AsyncMock()
        repo.get_all_users_dto = AsyncMock()
        repo.find_users_by_email_pattern = AsyncMock()
        return repo

    @pytest.fixture
    def profile_service(self, mock_repository):
        """Create a minimal ProfileService for integration testing (test-only)

        Core should not ship user-specific runtime services. For integration tests
        we define a simple local ProfileService that depends on a repository
        providing `get_user_dto`.
        """

        class ProfileService:
            def __init__(self, user_repository):
                self.user_repository = user_repository

            async def get_current_profile(self):
                # In real apps this would inspect Context or auth, tests patch Context
                from quadkit.primitives.context import Context

                user = Context.get("user")
                if user is None:
                    return None
                return await self.user_repository.get_user_dto(user.user_id)

        return ProfileService(mock_repository)

    @pytest.fixture
    def user_service(self, mock_repository):
        """Create a minimal UserManagementService for integration testing (test-only)."""

        class UserManagementService:
            def __init__(self, user_repository):
                self.user_repository = user_repository

            async def create_user(self, user_id: str, email: str, username: str):
                # For testing we simulate creation by delegating to repository
                await getattr(self.user_repository, "save", self.user_repository)

        return UserManagementService(mock_repository)

    @pytest.fixture
    def user_profile_projection(self):
        """Create UserProfileProjection instance"""
        try:
            from quadkit.events.projections.user_profile import UserProfileProjection

            return UserProfileProjection()
        except ImportError:
            pytest.skip(
                "quadkit.events module not available in isolated testing environment",
            )

    @pytest.fixture
    def context(self):
        """Create context fixture"""
        return Context

    @pytest.mark.asyncio
    async def test_complete_user_lifecycle_with_projection(
        self,
        profile_service,
        user_profile_projection,
    ):
        """Test complete user lifecycle: create -> update -> delete with projection"""
        user_id = "user-123"

        # Step 1: Simulate user registration event
        class UserCreatedEvent:
            def __init__(self):
                self.aggregate_id = user_id
                self.email = "john@example.com"
                self.username = "johndoe"

        await user_profile_projection.apply(UserCreatedEvent())

        # Verify user was created in projection
        profile = await user_profile_projection.get_user_profile(user_id)
        assert profile is not None
        assert profile["email"] == "john@example.com"
        assert profile["username"] == "johndoe"
        assert profile["is_active"] is True

        # Step 2: Simulate email change event
        class UserEmailChangedEvent:
            def __init__(self):
                self.aggregate_id = user_id
                self.new_email = "john.doe@example.com"

        await user_profile_projection.apply(UserEmailChangedEvent())

        # Verify email was updated
        profile = await user_profile_projection.get_user_profile(user_id)
        assert profile["email"] == "john.doe@example.com"

        # Step 3: Simulate name change event
        class UserNameChangedEvent:
            def __init__(self):
                self.aggregate_id = user_id
                self.new_name = "John Doe"

        await user_profile_projection.apply(UserNameChangedEvent())

        # Verify name was updated
        profile = await user_profile_projection.get_user_profile(user_id)
        assert profile["username"] == "John Doe"

        # Step 4: Simulate user deletion event
        class UserDeletedEvent:
            def __init__(self):
                self.aggregate_id = user_id

        await user_profile_projection.apply(UserDeletedEvent())

        # Verify user was marked inactive
        profile = await user_profile_projection.get_user_profile(user_id)
        assert profile["is_active"] is False

        # Verify user doesn't appear in active users list
        active_users = await user_profile_projection.get_active_users()
        user_ids = [user["id"] for user in active_users]
        assert user_id not in user_ids

    @pytest.mark.asyncio
    async def test_context_aware_service_with_projection(
        self,
        profile_service,
        user_profile_projection,
    ):
        """Test context-aware service working with event projections"""
        from unittest.mock import patch

        user_id = "12345678-1234-5678-1234-567812345678"  # Valid UUID

        # Mock Context to return authenticated user
        mock_user = Mock()
        mock_user.user_id = user_id
        mock_user.email = "jane@example.com"

        mock_context = Mock()
        mock_context.get.return_value = mock_user

        # Create user in projection via event
        class UserCreatedEvent:
            def __init__(self):
                self.aggregate_id = user_id
                self.email = "jane@example.com"
                self.username = "janesmith"

        await user_profile_projection.apply(UserCreatedEvent())

        # Mock the repository to return the profile
        mock_profile = Mock()
        mock_profile.id = user_id
        mock_profile.email = "jane@example.com"
        mock_profile.username = "janesmith"
        profile_service.user_repository.get_user_dto.return_value = mock_profile

        # Service should be able to get current user profile using context
        with patch("quadkit.contracts.core.context.Context", mock_context):
            profile = await profile_service.get_current_profile()

        assert profile is not None
        assert profile.id == user_id
        assert profile.email == "jane@example.com"

        # Verify the service used the user ID from context
        profile_service.user_repository.get_user_dto.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_multiple_users_projection_isolation(self, user_profile_projection):
        """Test that projection correctly handles multiple users independently"""
        # Create multiple users
        users_data = [
            ("user-1", "alice@example.com", "alice"),
            ("user-2", "bob@example.com", "bob"),
            ("user-3", "charlie@example.com", "charlie"),
        ]

        # Register all users
        for user_id, email, username in users_data:

            class UserCreatedEvent:
                def __init__(self, uid, em, un):
                    self.aggregate_id = uid
                    self.email = em
                    self.username = un

            await user_profile_projection.apply(
                UserCreatedEvent(user_id, email, username),
            )

        # Verify all users exist independently
        for user_id, expected_email, expected_username in users_data:
            profile = await user_profile_projection.get_user_profile(user_id)
            assert profile is not None
            assert profile["id"] == user_id
            assert profile["email"] == expected_email
            assert profile["username"] == expected_username
            assert profile["is_active"] is True

        # Update one user
        class UserEmailChangedEvent:
            def __init__(self):
                self.aggregate_id = "user-2"
                self.new_email = "bob.smith@example.com"

        await user_profile_projection.apply(UserEmailChangedEvent())

        # Verify only user-2 was updated
        profile_1 = await user_profile_projection.get_user_profile("user-1")
        assert profile_1["email"] == "alice@example.com"

        profile_2 = await user_profile_projection.get_user_profile("user-2")
        assert profile_2["email"] == "bob.smith@example.com"

        profile_3 = await user_profile_projection.get_user_profile("user-3")
        assert profile_3["email"] == "charlie@example.com"

    def test_projection_handles_correct_event_types(self, user_profile_projection):
        """Test that projection declares correct event types it handles"""
        handles = user_profile_projection.handles

        # Should handle exactly 4 event types
        assert len(handles) == 4

        # Check that the event type names are correct
        event_names = [cls.__name__ for cls in handles]
        expected_events = {
            "UserCreatedEvent",
            "UserEmailChangedEvent",
            "UserNameChangedEvent",
            "UserDeletedEvent",
        }
        assert set(event_names) == expected_events
