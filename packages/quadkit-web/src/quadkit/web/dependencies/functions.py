from __future__ import annotations

from typing import Any

from starlette import status
from starlette.requests import Request

from quadkit.web.dependencies.state import RequestState
from quadkit.web.exceptions import HTTPError


async def get_request_id(request: Request) -> str:
    """Get request ID from state."""
    request_id = RequestState.require(request, "request_id")
    if not isinstance(request_id, str):
        raise HTTPError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Request ID must be a string",
        )
    return request_id


async def get_current_user_optional(request: Request) -> Any | None:
    """Get current user from state (optional)."""
    return RequestState.get(request, "user", object, default=None)


async def get_current_user_required(request: Request) -> Any:
    """Get current user from state (required)."""
    user = RequestState.get(request, "user", object, default=None)
    if user is None:
        raise HTTPError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_database(request: Request) -> Any:
    """Get database connection from state."""
    return RequestState.require(request, "db")
