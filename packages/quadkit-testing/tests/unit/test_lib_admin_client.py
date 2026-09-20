"""AdminTestClient and admin response helpers."""

from __future__ import annotations

from typing import Any

import pytest
from quadkit.testing.lib.admin_helpers import (
    AdminResponse,
    AdminTestClient,
    make_resource_record,
)

# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(
        self,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        text: str = "body",
        json_data: Any = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._text = text
        self._json = json_data

    @property
    def text(self) -> str:
        if self._text is None:
            raise RuntimeError("content unavailable")
        return self._text

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("not json")
        return self._json


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.resp = _FakeResp()

    def set(self, **kwargs: Any) -> None:
        self.resp = _FakeResp(**kwargs)

    def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        self.calls.append(("GET", url, params, headers))
        return self.resp

    def post(self, url: str, data: dict | None = None, headers: dict | None = None):
        self.calls.append(("POST", url, data, headers))
        return self.resp

    def delete(self, url: str, headers: dict | None = None):
        self.calls.append(("DELETE", url, None, headers))
        return self.resp


def _admin() -> tuple[AdminTestClient, _FakeClient]:
    client = _FakeClient()
    return AdminTestClient(client, default_headers={"X-Test": "1"}), client


# ---------------------------------------------------------------------------
# admin_helpers
# ---------------------------------------------------------------------------


def test_admin_response_htmx_helpers() -> None:
    resp = AdminResponse(
        status_code=200,
        headers={"HX-Redirect": "/x", "hx-trigger": "saved"},
    )
    assert resp.is_htmx_redirect() is True
    assert resp.htmx_redirect_url() == "/x"
    assert resp.htmx_trigger() == "saved"

    plain = AdminResponse(status_code=200, headers={"Content-Type": "text/html"})
    assert plain.is_htmx_redirect() is False
    assert plain.htmx_redirect_url() is None
    assert plain.htmx_trigger() is None


def test_admin_url_building_and_prefix_strip() -> None:
    admin, _ = _admin()
    assert admin.url("user") == "/admin/user"
    assert admin.url("user", "123", "edit") == "/admin/user/123/edit"
    stripped = AdminTestClient(_FakeClient(), prefix="/admin/")
    assert stripped.url("item") == "/admin/item"


def test_admin_crud_helpers() -> None:
    admin, fake = _admin()

    admin.list("user", params={"page": "2"})
    admin.detail("user", "42")
    admin.create("user", {"name": "a"})
    admin.update("user", "42", {"name": "b"})
    admin.delete("user", "42")
    admin.bulk_action("user", "archive", ["1", "2"])
    admin.search("user", "jo")

    assert [c[0] for c in fake.calls] == [
        "GET",
        "GET",
        "POST",
        "POST",
        "DELETE",
        "POST",
        "GET",
    ]
    assert fake.calls[0][1] == "/admin/user"
    assert fake.calls[0][2] == {"page": "2"}
    assert fake.calls[1][1] == "/admin/user/42"
    assert fake.calls[2][2] == {"name": "a"}
    assert fake.calls[3][1] == "/admin/user/42/edit"
    assert fake.calls[4][1] == "/admin/user/42"
    assert fake.calls[5][2] == {"action": "archive", "ids": "1,2"}
    assert fake.calls[6][2] == {"search": "jo"}
    # Default HX header + custom header on every call.
    for _, _, _, headers in fake.calls:
        assert headers["HX-Request"] == "true"
        assert headers["X-Test"] == "1"


def test_admin_wrap_json_text_and_errors() -> None:
    admin, fake = _admin()
    fake.set(
        status_code=200,
        headers={"content-type": "application/json"},
        json_data={"ok": True},
        text="{}",
    )
    resp = admin.list("user")
    assert resp.json_data == {"ok": True}
    assert resp.text == "{}"

    # Non-JSON content type → json_data stays None even if json() works.
    fake.set(status_code=204, headers={"content-type": "text/html"})
    assert admin.detail("user", "1").json_data is None

    # json() raising → swallowed, text still captured.
    fake.set(status_code=200, headers={"content-type": "application/json"})
    assert admin.detail("user", "1").json_data is None

    # resp.text raising → swallowed.
    fake.set(status_code=200, text=None)
    resp = admin.list("user")
    assert resp.text == ""


def test_admin_assertions() -> None:
    AdminTestClient.assert_ok(AdminResponse(200))
    AdminTestClient.assert_unprocessable(AdminResponse(422))
    AdminTestClient.assert_contains(AdminResponse(200, text="hello world"), "lo wo")
    AdminTestClient.assert_htmx_trigger(
        AdminResponse(200, headers={"HX-Trigger": "saved,flash"}), "saved"
    )
    AdminTestClient.assert_redirect(AdminResponse(302, headers={"location": "/x"}))
    AdminTestClient.assert_redirect(AdminResponse(200, headers={"HX-Redirect": "/x"}))

    with pytest.raises(AssertionError, match="Expected HTTP 200, got 500"):
        AdminTestClient.assert_ok(AdminResponse(500, text="boom"))
    with pytest.raises(AssertionError, match="Expected a redirect"):
        AdminTestClient.assert_redirect(AdminResponse(200))
    with pytest.raises(AssertionError, match="Expected to find"):
        AdminTestClient.assert_contains(AdminResponse(200, text="nope"), "yes")
    with pytest.raises(AssertionError, match="Expected HX-Trigger"):
        AdminTestClient.assert_htmx_trigger(AdminResponse(200), "saved")
    with pytest.raises(AssertionError, match="Expected HTTP 422, got 200"):
        AdminTestClient.assert_unprocessable(AdminResponse(200))


def test_make_resource_record() -> None:
    rec = make_resource_record("user", name="Alice")
    assert rec["_type"] == "user"
    assert rec["name"] == "Alice"
    assert rec["id"]
    assert rec["created_at"] == "2024-01-01T00:00:00Z"
    rec2 = make_resource_record()
    assert rec2["_type"] == "item"
    assert rec2["id"] != rec["id"]


# ---------------------------------------------------------------------------
