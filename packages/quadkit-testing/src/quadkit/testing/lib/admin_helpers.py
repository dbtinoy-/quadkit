"""Admin-specific test helpers for the optional provider tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdminResponse:
    """Lightweight wrapper around a raw response for admin assertions.

    Attributes:
        status_code: HTTP status code.
        headers: Response headers dict.
        text: Response body as text.
        json_data: Parsed JSON body (``None`` if not JSON).
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    json_data: Any = None

    def is_htmx_redirect(self) -> bool:
        """Return ``True`` if the response contains ``HX-Redirect`` header."""
        return "hx-redirect" in {k.lower() for k in self.headers}

    def htmx_redirect_url(self) -> str | None:
        """Return the ``HX-Redirect`` URL if present."""
        for k, v in self.headers.items():
            if k.lower() == "hx-redirect":
                return v
        return None

    def htmx_trigger(self) -> str | None:
        """Return the ``HX-Trigger`` header value if present."""
        for k, v in self.headers.items():
            if k.lower() == "hx-trigger":
                return v
        return None


class AdminTestClient:
    """Test client with helpers for the optional provider endpoints.

    Wraps a Starlette ``TestClient`` (or any httpx-compatible sync client)
    and provides assertion helpers and convenience methods for CRUD operations.

    Args:
        client: An httpx-compatible test client (e.g. Starlette ``TestClient``).
        prefix: Admin URL prefix (default ``"/admin"``).
        default_headers: Headers added to every request.
    """

    def __init__(
        self,
        client: Any,
        prefix: str = "/admin",
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix.rstrip("/")
        self._headers: dict[str, str] = {
            "HX-Request": "true",
            **(default_headers or {}),
        }

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def url(self, resource: str, *parts: str) -> str:
        """Build an admin resource URL.

        Args:
            resource: Resource name (e.g. ``"user"``).
            *parts: Additional path segments.

        Returns:
            Full URL string, e.g. ``"/admin/user/123/edit"``.
        """
        segments = [self._prefix, resource, *parts]
        return "/" + "/".join(s.strip("/") for s in segments if s)

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def list(
        self, resource: str, params: dict[str, str] | None = None
    ) -> AdminResponse:
        """GET the list page for a resource."""
        resp = self._client.get(
            self.url(resource), params=params, headers=self._headers
        )
        return self._wrap(resp)

    def detail(self, resource: str, record_id: str) -> AdminResponse:
        """GET the detail page for a record."""
        resp = self._client.get(self.url(resource, record_id), headers=self._headers)
        return self._wrap(resp)

    def create(self, resource: str, data: dict[str, Any]) -> AdminResponse:
        """POST to create a new record."""
        resp = self._client.post(self.url(resource), data=data, headers=self._headers)
        return self._wrap(resp)

    def update(
        self, resource: str, record_id: str, data: dict[str, Any]
    ) -> AdminResponse:
        """POST to update an existing record."""
        resp = self._client.post(
            self.url(resource, record_id, "edit"), data=data, headers=self._headers
        )
        return self._wrap(resp)

    def delete(self, resource: str, record_id: str) -> AdminResponse:
        """POST (or DELETE) to delete a record."""
        resp = self._client.delete(self.url(resource, record_id), headers=self._headers)
        return self._wrap(resp)

    def bulk_action(self, resource: str, action: str, ids: list[str]) -> AdminResponse:  # type: ignore[valid-type]
        """POST a bulk action."""
        data = {"action": action, "ids": ",".join(ids)}
        resp = self._client.post(
            self.url(resource, "bulk"), data=data, headers=self._headers
        )
        return self._wrap(resp)

    def search(self, resource: str, query: str) -> AdminResponse:
        """GET the list page with a search query."""
        return self.list(resource, params={"search": query})

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def assert_status(resp: AdminResponse, expected: int) -> None:
        """Assert response has expected HTTP status code."""
        assert resp.status_code == expected, (
            f"Expected HTTP {expected}, got {resp.status_code}.\n"
            f"Body: {resp.text[:500]}"
        )

    @staticmethod
    def assert_ok(resp: AdminResponse) -> None:
        """Assert response is 200 OK."""
        AdminTestClient.assert_status(resp, 200)

    @staticmethod
    def assert_redirect(resp: AdminResponse) -> None:
        """Assert response is an HTMX or standard redirect."""
        is_htmx = resp.is_htmx_redirect()
        is_standard = resp.status_code in (301, 302, 303, 307, 308)
        assert is_htmx or is_standard, (
            f"Expected a redirect (302 or HX-Redirect), got HTTP {resp.status_code}. "
            f"Headers: {resp.headers}"
        )

    @staticmethod
    def assert_unprocessable(resp: AdminResponse) -> None:
        """Assert response is HTTP 422 (validation error)."""
        AdminTestClient.assert_status(resp, 422)

    @staticmethod
    def assert_contains(resp: AdminResponse, text: str) -> None:
        """Assert response body contains *text*."""
        assert text in resp.text, (
            f"Expected to find {text!r} in response body.\n"
            f"Body snippet: {resp.text[:300]}"
        )

    @staticmethod
    def assert_htmx_trigger(resp: AdminResponse, event: str) -> None:
        """Assert ``HX-Trigger`` header contains *event*."""
        trigger = resp.htmx_trigger() or ""
        assert event in trigger, (
            f"Expected HX-Trigger to contain {event!r}, got: {trigger!r}"
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap(resp: Any) -> AdminResponse:
        """Wrap a raw httpx/requests Response into :class:`AdminResponse`."""
        headers: dict[str, str] = {}
        for k, v in (resp.headers or {}).items():
            headers[str(k)] = str(v)

        text = ""
        try:
            text = resp.text
        except Exception:  # noqa: BLE001, S110
            pass

        json_data = None
        try:
            if "application/json" in headers.get("content-type", ""):
                json_data = resp.json()
        except Exception:  # noqa: BLE001, S110
            pass

        return AdminResponse(
            status_code=resp.status_code,
            headers=headers,
            text=text,
            json_data=json_data,
        )


def make_resource_record(resource_type: str = "item", **fields: Any) -> dict[str, Any]:
    """Create a minimal resource record dict for testing.

    Provides sensible defaults so callers only need to specify the fields
    relevant to the test.

    Args:
        resource_type: Record type tag (stored in ``_type``).
        **fields: Field values to override defaults.

    Returns:
        Dict representing the resource record.

    Example::

        user = make_resource_record("user", name="Alice", email="a@b.com")
        # {"id": "test-user-1", "_type": "user", "name": "Alice", ...}
    """
    import uuid

    defaults: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "_type": resource_type,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }
    defaults.update(fields)
    return defaults


__all__ = [
    "AdminResponse",
    "AdminTestClient",
    "make_resource_record",
]
