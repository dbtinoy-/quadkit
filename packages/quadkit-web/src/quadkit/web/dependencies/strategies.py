"""Resolution strategies for web-related dependencies."""

from __future__ import annotations

from typing import Any

from quadkit.di.extensions.strategies import ResolutionStrategy


class WebParameterStrategy(ResolutionStrategy):
    """Resolves path params, query params, headers from the request.

    This strategy is used by quadkit-web to inject web parameters
    (path, query, headers) alongside DI services.
    """

    def __init__(
        self,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, str | list[str]] | None = None,
        headers: dict[str, str] | None = None,
        request: Any = None,
    ):
        self._path = path_params or {}
        self._query = query_params or {}
        self._headers = headers or {}
        self._request = request

    async def resolve(
        self,
        param_name: str,
        param_type: type,
        default: Any,
    ) -> tuple[bool, Any]:
        # Path parameters
        if param_name in self._path:
            try:
                return True, param_type(self._path[param_name])
            except (ValueError, TypeError):
                return True, self._path[param_name]

        # Query parameters (handle both single and list values)
        if param_name in self._query:
            value = self._query[param_name]
            if isinstance(value, list):
                try:
                    return True, [param_type(v) for v in value]
                except (ValueError, TypeError):
                    return True, value
            else:
                try:
                    return True, param_type(value)
                except (ValueError, TypeError):
                    return True, value

        # Header parameters (case-insensitive)
        header_key = param_name.lower().replace("_", "-")
        if header_key in self._headers:
            return True, self._headers[header_key]

        # Request object - check if param_type matches
        if self._request is not None and (
            param_type is type(self._request)
            or (
                hasattr(param_type, "__name__")
                and param_type.__name__ == type(self._request).__name__
            )
        ):
            return True, self._request

        return False, None
