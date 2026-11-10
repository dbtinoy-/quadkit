"""Tests for the MCP connectors: github, google_drive, slack, filesystem.

Covers tool dispatch, API error surfaces (HTTP/JSON failures must become
tool *error results*, never exceptions), sandbox security for the
filesystem connector, and async hygiene for the HTTP helpers.
"""

from __future__ import annotations

import base64
from pathlib import Path
import sys
import types
from typing import Any, Self

import aiohttp
import pytest

from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector
from quadkit.ai.mcp.connectors.github import GitHubConnector
from quadkit.ai.mcp.connectors.google_drive import GoogleDriveConnector
from quadkit.ai.mcp.connectors.slack import SlackConnector
from quadkit.contracts.mcp.exceptions import MCPToolCallError
from quadkit.serialization import loads_str

# ---------------------------------------------------------------------------
# aiohttp fakes
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Stands in for an aiohttp response context manager."""

    def __init__(
        self,
        payload: Any = None,
        *,
        status: int = 200,
        json_error: Exception | None = None,
        text: str = "",
    ) -> None:
        self._payload = payload
        self._status = status
        self._json_error = json_error
        self._text = text

    @property
    def status(self) -> int:
        return self._status

    async def json(self, content_type: str | None = None) -> Any:
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeSession:
    """Stands in for ``aiohttp.ClientSession``; records every request."""

    def __init__(
        self,
        get_response: _FakeResponse | None = None,
        post_response: _FakeResponse | None = None,
    ) -> None:
        self._get_response = get_response or _FakeResponse({})
        self._post_response = post_response or _FakeResponse({})
        self.request_headers: dict[str, str] | None = None
        self.requests: list[tuple[str, str, Any]] = []

    def get(self, url: str, params: Any = None, timeout: Any = None) -> _FakeResponse:
        self.requests.append(("GET", url, params))
        return self._get_response

    def post(self, url: str, json: Any = None, timeout: Any = None) -> _FakeResponse:
        self.requests.append(("POST", url, json))
        return self._post_response

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


@pytest.fixture
def fake_aiohttp(monkeypatch: pytest.MonkeyPatch) -> _FakeSession:
    """Install a recording fake for ``aiohttp.ClientSession``."""
    session = _FakeSession()

    def _factory(headers: dict[str, str] | None = None, **_: Any) -> _FakeSession:
        session.request_headers = headers
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", _factory)
    return session


# ---------------------------------------------------------------------------
# google-auth fakes (not installed in the QA venv — simulate the import)
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Stand-in for google.auth.transport.requests.Request."""


class _FakeGoogleCreds:
    def __init__(self, *, valid: bool = True, token: str = "tok-1") -> None:  # noqa: S107 -- fake credential for tests
        self.valid = valid
        self.token = token
        self.refresh_calls = 0
        self.subject: str | None = None

    def refresh(self, request: Any) -> None:
        assert isinstance(request, _FakeRequest)
        self.refresh_calls += 1
        self.token = f"refreshed-{self.refresh_calls}"
        self.valid = True

    def with_subject(self, email: str) -> _FakeGoogleCreds:
        self.subject = email
        return self


@pytest.fixture
def fake_google(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Pretend google-auth is installed; capture from_service_account_info."""
    captured: dict[str, Any] = {}

    class _CredsFactory:
        @classmethod
        def from_service_account_info(cls, info: Any, scopes: Any) -> _FakeGoogleCreds:
            captured["info"] = info
            captured["scopes"] = scopes
            return _FakeGoogleCreds()

    transport_requests = types.ModuleType("google.auth.transport.requests")
    transport_requests.Request = _FakeRequest  # type: ignore[attr-defined]
    service_account = types.ModuleType("google.oauth2.service_account")
    service_account.Credentials = _CredsFactory  # type: ignore[attr-defined]

    modules = {
        "google": types.ModuleType("google"),
        "google.auth": types.ModuleType("google.auth"),
        "google.auth.transport": types.ModuleType("google.auth.transport"),
        "google.auth.transport.requests": transport_requests,
        "google.oauth2": types.ModuleType("google.oauth2"),
        "google.oauth2.service_account": service_account,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    return captured


def _drive(conn: GoogleDriveConnector, creds: _FakeGoogleCreds) -> GoogleDriveConnector:
    conn._credentials = creds
    return conn


# ---------------------------------------------------------------------------
# GitHub connector
# ---------------------------------------------------------------------------


class TestGitHubConnector:
    def test_requires_non_empty_token(self) -> None:
        with pytest.raises(ValueError, match="non-empty token"):
            GitHubConnector("")

    @pytest.mark.asyncio
    async def test_list_tools_exposes_five_tools(self) -> None:
        tools = await GitHubConnector("tok").list_tools()
        assert [t["name"] for t in tools] == [
            "github_list_repos",
            "github_get_file",
            "github_create_issue",
            "github_search_code",
            "github_list_issues",
        ]

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(MCPToolCallError, match="Unknown GitHub tool"):
            await GitHubConnector("tok").call_tool("nope", {})

    @pytest.mark.asyncio
    async def test_list_repos_success(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            [
                {
                    "name": "repo1",
                    "description": "d",
                    "html_url": "https://github.com/o/repo1",
                }
            ]
        )
        result = await GitHubConnector("tok").call_tool(
            "github_list_repos", {"owner": "o"}
        )
        assert not result.is_error
        assert loads_str(result.content[0]["text"]) == [
            {"name": "repo1", "description": "d", "url": "https://github.com/o/repo1"}
        ]
        method, url, params = fake_aiohttp.requests[0]
        assert method == "GET"
        assert url == "https://api.github.com/users/o/repos"
        assert params == {"type": "public", "per_page": 30}
        assert fake_aiohttp.request_headers is not None
        assert fake_aiohttp.request_headers["Authorization"] == "Bearer tok"

    @pytest.mark.asyncio
    async def test_list_repos_api_error(self, fake_aiohttp: _FakeSession) -> None:
        sentinel = "SENTINEL-sensitive-github-error"
        fake_aiohttp._get_response = _FakeResponse({"message": sentinel})
        result = await GitHubConnector("tok").call_tool(
            "github_list_repos", {"owner": "o"}
        )
        assert result.is_error
        assert "GitHub API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_per_page_capped_at_100(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._get_response = _FakeResponse([])
        await GitHubConnector("tok").call_tool(
            "github_list_repos", {"owner": "o", "per_page": 1000}
        )
        assert fake_aiohttp.requests[0][2]["per_page"] == 100

    @pytest.mark.asyncio
    async def test_enterprise_api_url_override(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._get_response = _FakeResponse([])
        conn = GitHubConnector("tok", api_url="https://ghe.example.com/api/v3/")
        await conn.call_tool("github_list_repos", {"owner": "o"})
        assert fake_aiohttp.requests[0][1] == (
            "https://ghe.example.com/api/v3/users/o/repos"
        )

    @pytest.mark.asyncio
    async def test_get_file_decodes_base64_with_ref(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            {"encoding": "base64", "content": base64.b64encode(b"hello world").decode()}
        )
        result = await GitHubConnector("tok").call_tool(
            "github_get_file",
            {"owner": "o", "repo": "r", "path": "a.py", "ref": "main"},
        )
        assert not result.is_error
        assert result.content[0]["text"] == "hello world"
        _, url, params = fake_aiohttp.requests[0]
        assert url == "https://api.github.com/repos/o/r/contents/a.py"
        assert params == {"ref": "main"}

    @pytest.mark.asyncio
    async def test_get_file_api_error(self, fake_aiohttp: _FakeSession) -> None:
        sentinel = "SENTINEL-sensitive-github-file-error"
        fake_aiohttp._get_response = _FakeResponse({"message": sentinel})
        result = await GitHubConnector("tok").call_tool(
            "github_get_file", {"owner": "o", "repo": "r", "path": "x"}
        )
        assert result.is_error
        assert "GitHub API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_get_file_non_dict_response_is_error(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._get_response = _FakeResponse(["unexpected"])
        result = await GitHubConnector("tok").call_tool(
            "github_get_file", {"owner": "o", "repo": "r", "path": "x"}
        )
        assert result.is_error

    @pytest.mark.asyncio
    async def test_create_issue_success_with_labels(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._post_response = _FakeResponse(
            {"number": 7, "html_url": "https://github.com/o/r/issues/7"}
        )
        result = await GitHubConnector("tok").call_tool(
            "github_create_issue",
            {"owner": "o", "repo": "r", "title": "t", "labels": ["bug"]},
        )
        assert not result.is_error
        assert loads_str(result.content[0]["text"]) == {
            "issue_number": 7,
            "url": "https://github.com/o/r/issues/7",
        }
        _, url, payload = fake_aiohttp.requests[0]
        assert url == "https://api.github.com/repos/o/r/issues"
        assert payload == {"title": "t", "body": "", "labels": ["bug"]}

    @pytest.mark.asyncio
    async def test_create_issue_api_error(self, fake_aiohttp: _FakeSession) -> None:
        sentinel = "SENTINEL-sensitive-github-issue-error"
        fake_aiohttp._post_response = _FakeResponse({"message": sentinel})
        result = await GitHubConnector("tok").call_tool(
            "github_create_issue", {"owner": "o", "repo": "r", "title": "t"}
        )
        assert result.is_error
        assert "GitHub API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_search_code(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            {
                "items": [
                    {
                        "name": "f.py",
                        "path": "src/f.py",
                        "repository": {"full_name": "o/r"},
                        "html_url": "u",
                    }
                ]
            }
        )
        result = await GitHubConnector("tok").call_tool(
            "github_search_code", {"query": "foo language:python"}
        )
        items = loads_str(result.content[0]["text"])
        assert items[0]["repo"] == "o/r"
        assert fake_aiohttp.requests[0][1] == "https://api.github.com/search/code"
        assert fake_aiohttp.requests[0][2]["q"] == "foo language:python"

    @pytest.mark.asyncio
    async def test_list_issues_excludes_pull_requests(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            [
                {"number": 1, "title": "issue", "state": "open", "html_url": "u1"},
                {
                    "number": 2,
                    "title": "pr",
                    "state": "open",
                    "html_url": "u2",
                    "pull_request": {},
                },
            ]
        )
        result = await GitHubConnector("tok").call_tool(
            "github_list_issues", {"owner": "o", "repo": "r"}
        )
        assert [i["number"] for i in loads_str(result.content[0]["text"])] == [1]

    @pytest.mark.asyncio
    async def test_get_http_failure_becomes_tool_error(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        # Non-JSON/empty response bodies used to escape as raw exceptions.
        sentinel = "SENTINEL-sensitive-github-http-error"
        fake_aiohttp._get_response = _FakeResponse(json_error=ValueError(sentinel))
        result = await GitHubConnector("tok").call_tool(
            "github_list_repos", {"owner": "o"}
        )
        assert result.is_error
        assert "GitHub API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_post_http_failure_becomes_tool_error(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        sentinel = "SENTINEL-sensitive-github-post-error"
        fake_aiohttp._post_response = _FakeResponse(
            json_error=aiohttp.ClientError(sentinel)
        )
        result = await GitHubConnector("tok").call_tool(
            "github_create_issue", {"owner": "o", "repo": "r", "title": "t"}
        )
        assert result.is_error
        assert "GitHub API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_resource_repo_file_and_invalid(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        conn = GitHubConnector("tok")
        fake_aiohttp._get_response = _FakeResponse({"name": "r", "full_name": "o/r"})
        out = await conn.read_resource("github://o/r")
        assert out["contents"][0]["uri"] == "github://o/r"
        assert loads_str(out["contents"][0]["text"])["full_name"] == "o/r"

        fake_aiohttp._get_response = _FakeResponse(
            {"encoding": "base64", "content": base64.b64encode(b"x").decode()}
        )
        out2 = await conn.read_resource("github://o/r/src/a.py")
        assert out2["contents"][0]["text"] == "x"

        out3 = await conn.read_resource("github://")
        assert out3["contents"][0]["text"] == "Invalid URI"


# ---------------------------------------------------------------------------
# Google Drive connector
# ---------------------------------------------------------------------------


class TestGoogleDriveConnector:
    def test_requires_service_account_json(self) -> None:
        with pytest.raises(ValueError, match="service_account_json"):
            GoogleDriveConnector("")

    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        tools = await GoogleDriveConnector("{}").list_tools()
        assert [t["name"] for t in tools] == ["gdrive_list_files", "gdrive_read_file"]

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(MCPToolCallError, match="Unknown Google Drive tool"):
            await GoogleDriveConnector("{}").call_tool("nope", {})

    @pytest.mark.asyncio
    async def test_list_resources(self) -> None:
        res = await GoogleDriveConnector("{}").list_resources()
        assert [r["uri"] for r in res] == ["gdrive://files"]

    @pytest.mark.asyncio
    async def test_tools_error_when_google_auth_missing(self, monkeypatch) -> None:
        # Force the optional dependency import to fail, even if the test
        # environment happens to have google-auth installed.
        monkeypatch.setitem(sys.modules, "google.auth.transport.requests", None)
        result = await GoogleDriveConnector("{}").call_tool("gdrive_list_files", {})
        assert result.is_error
        assert "google-auth is required" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_invalid_credentials_refreshed_off_event_loop(
        self, fake_google: dict[str, Any]
    ) -> None:
        conn = GoogleDriveConnector("{}")
        creds = _FakeGoogleCreds(valid=False, token="")
        conn._credentials = creds
        token = await conn._access_token()
        assert token == "refreshed-1"
        assert creds.refresh_calls == 1

    @pytest.mark.asyncio
    async def test_credentials_built_from_json_with_impersonation(
        self, fake_google: dict[str, Any]
    ) -> None:
        conn = GoogleDriveConnector(
            '{"client_email": "svc@x.iam.gserviceaccount.com"}',
            impersonated_email="u@x.com",
        )
        await conn._access_token()
        assert fake_google["info"]["client_email"] == "svc@x.iam.gserviceaccount.com"
        assert conn._credentials is not None
        assert conn._credentials.subject == "u@x.com"

    @pytest.mark.asyncio
    async def test_list_files_query_and_params(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        fake_aiohttp._get_response = _FakeResponse(
            {"files": [{"id": "f1", "name": "a.txt"}]}
        )
        result = await conn.call_tool(
            "gdrive_list_files", {"query": "name contains 'a'", "limit": 5}
        )
        assert not result.is_error
        assert loads_str(result.content[0]["text"]) == [{"id": "f1", "name": "a.txt"}]
        _, url, params = fake_aiohttp.requests[0]
        assert url == "https://www.googleapis.com/drive/v3/files"
        assert (
            params["q"] == "'root' in parents and trashed=false and (name contains 'a')"
        )
        assert params["pageSize"] == 5
        assert fake_aiohttp.request_headers is not None
        assert fake_aiohttp.request_headers["Authorization"] == "Bearer tok-1"

    @pytest.mark.asyncio
    async def test_list_files_drive_error(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        sentinel = "SENTINEL-sensitive-drive-error"
        fake_aiohttp._get_response = _FakeResponse({"error": {"message": sentinel}})
        result = await conn.call_tool("gdrive_list_files", {})
        assert result.is_error
        assert "Google Drive request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_drive_http_failure_becomes_tool_error(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        fake_aiohttp._get_response = _FakeResponse(
            json_error=ValueError("No response content")
        )
        result = await conn.call_tool("gdrive_list_files", {})
        assert result.is_error
        assert "Drive request failed" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_file_requires_file_id(self) -> None:
        result = await GoogleDriveConnector("{}").call_tool("gdrive_read_file", {})
        assert result.is_error
        assert "file_id" in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_file_exports_google_doc(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        fake_aiohttp._get_response = _FakeResponse(
            {"mimeType": "application/vnd.google-apps.document", "name": "doc"},
            text="exported text",
        )
        result = await conn.call_tool("gdrive_read_file", {"file_id": "f1"})
        assert not result.is_error
        assert result.content[0]["text"] == "exported text"
        assert fake_aiohttp.requests[1][1].endswith("/files/f1/export")
        assert fake_aiohttp.requests[1][2] == {"mimeType": "text/plain"}

    @pytest.mark.asyncio
    async def test_read_file_binary_returns_note_without_phantom_tool(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        fake_aiohttp._get_response = _FakeResponse(
            {"mimeType": "application/pdf", "name": "x.pdf"}
        )
        result = await conn.call_tool("gdrive_read_file", {"file_id": "f1"})
        data = loads_str(result.content[0]["text"])
        assert data["mimeType"] == "application/pdf"
        # The old note referenced a tool that does not exist.
        assert "gdrive_get_download_url" not in data["note"]
        assert data["note"]

    @pytest.mark.asyncio
    async def test_read_resource(
        self, fake_aiohttp: _FakeSession, fake_google: dict[str, Any]
    ) -> None:
        conn = _drive(GoogleDriveConnector("{}"), _FakeGoogleCreds())
        fake_aiohttp._get_response = _FakeResponse({"files": []})
        out = await conn.read_resource("gdrive://files")
        assert out["contents"][0]["text"] == "[]"
        fake_aiohttp._get_response = _FakeResponse(
            {"mimeType": "application/pdf", "name": "x.pdf"}
        )
        out2 = await conn.read_resource("gdrive://f1")
        assert out2["contents"][0]["uri"] == "gdrive://f1"


# ---------------------------------------------------------------------------
# Slack connector
# ---------------------------------------------------------------------------


class TestSlackConnector:
    def test_requires_non_empty_token(self) -> None:
        with pytest.raises(ValueError, match="non-empty bot_token"):
            SlackConnector("")

    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        tools = await SlackConnector("xoxb-tok").list_tools()
        assert [t["name"] for t in tools] == [
            "slack_list_channels",
            "slack_get_history",
            "slack_post_message",
            "slack_search_messages",
        ]

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self) -> None:
        with pytest.raises(MCPToolCallError, match="Unknown Slack tool"):
            await SlackConnector("t").call_tool("nope", {})

    @pytest.mark.asyncio
    async def test_list_resources_is_static(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Discovery must not hit the network — a round-trip here would slow
        # tool listing and burn rate limit.
        def _boom(*_args: Any, **_kwargs: Any) -> None:
            raise AssertionError("list_resources must not touch the network")

        monkeypatch.setattr(aiohttp, "ClientSession", _boom)
        res = await SlackConnector("xoxb-tok").list_resources()
        assert [r["uri"] for r in res] == ["slack://channels"]

    @pytest.mark.asyncio
    async def test_list_channels(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            {
                "ok": True,
                "channels": [{"id": "C1", "name": "general", "topic": {"value": "hi"}}],
            }
        )
        result = await SlackConnector("t").call_tool("slack_list_channels", {})
        assert loads_str(result.content[0]["text"]) == [
            {"id": "C1", "name": "general", "topic": "hi"}
        ]
        assert fake_aiohttp.requests[0][2]["types"] == "public_channel"
        assert fake_aiohttp.request_headers is not None
        assert fake_aiohttp.request_headers["Authorization"] == "Bearer t"

    @pytest.mark.asyncio
    async def test_slack_error_surfaces(self, fake_aiohttp: _FakeSession) -> None:
        sentinel = "SENTINEL-sensitive-slack-error"
        fake_aiohttp._get_response = _FakeResponse({"ok": False, "error": sentinel})
        result = await SlackConnector("t").call_tool("slack_list_channels", {})
        assert result.is_error
        assert "Slack API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_get_history_strips_hash_and_caps_limit(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            {"ok": True, "messages": [{"ts": "1", "user": "u", "text": "m"}]}
        )
        conn = SlackConnector("t", max_messages=5)
        result = await conn.call_tool(
            "slack_get_history", {"channel": "#general", "limit": 50}
        )
        params = fake_aiohttp.requests[0][2]
        assert params["channel"] == "general"
        assert params["limit"] == 5
        assert loads_str(result.content[0]["text"])[0]["text"] == "m"

    @pytest.mark.asyncio
    async def test_post_message(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._post_response = _FakeResponse(
            {"ok": True, "ts": "123.45", "channel": "C1"}
        )
        result = await SlackConnector("t").call_tool(
            "slack_post_message", {"channel": "C1", "text": "hi"}
        )
        assert loads_str(result.content[0]["text"]) == {"ts": "123.45", "channel": "C1"}

    @pytest.mark.asyncio
    async def test_post_message_requires_args(self) -> None:
        result = await SlackConnector("t").call_tool(
            "slack_post_message", {"channel": "C1"}
        )
        assert result.is_error

    @pytest.mark.asyncio
    async def test_search_messages(self, fake_aiohttp: _FakeSession) -> None:
        fake_aiohttp._get_response = _FakeResponse(
            {
                "ok": True,
                "messages": {
                    "matches": [
                        {
                            "channel": {"name": "general"},
                            "text": "x",
                            "ts": "1",
                            "permalink": "p",
                        }
                    ]
                },
            }
        )
        result = await SlackConnector("t").call_tool(
            "slack_search_messages", {"query": "x"}
        )
        assert loads_str(result.content[0]["text"])[0]["permalink"] == "p"

    @pytest.mark.asyncio
    async def test_http_failure_becomes_tool_error(
        self, fake_aiohttp: _FakeSession
    ) -> None:
        sentinel = "SENTINEL-sensitive-slack-http-error"
        fake_aiohttp._get_response = _FakeResponse(
            json_error=aiohttp.ClientError(sentinel)
        )
        result = await SlackConnector("t").call_tool("slack_list_channels", {})
        assert result.is_error
        assert "Slack API request failed" in result.content[0]["text"]
        assert sentinel not in result.content[0]["text"]

    @pytest.mark.asyncio
    async def test_read_resource(self, fake_aiohttp: _FakeSession) -> None:
        conn = SlackConnector("t")
        fake_aiohttp._get_response = _FakeResponse({"ok": True, "channels": []})
        out = await conn.read_resource("slack://channels")
        assert out["contents"][0]["text"] == "[]"
        fake_aiohttp._get_response = _FakeResponse({"ok": True, "messages": []})
        out2 = await conn.read_resource("slack://channel/C1")
        assert out2["contents"][0]["uri"] == "slack://channel/C1"


# ---------------------------------------------------------------------------
# Filesystem connector
# ---------------------------------------------------------------------------


class TestFilesystemConnector:
    def test_requires_existing_root(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            FilesystemConnector("")
        with pytest.raises(ValueError, match="does not exist"):
            FilesystemConnector("/no/such/dir/xyz")

    @pytest.fixture
    def sandbox(self, tmp_path: Path) -> Path:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "a.txt").write_text("alpha")
        (tmp_path / "docs" / "b.md").write_text("# b")
        return tmp_path

    @pytest.mark.asyncio
    async def test_read_write_list_search(self, sandbox: Path) -> None:
        conn = FilesystemConnector(str(sandbox))
        r = await conn.call_tool("read_file", {"path": "docs/a.txt"})
        assert r.content[0]["text"] == "alpha"
        r2 = await conn.call_tool(
            "write_file", {"path": "docs/new.txt", "content": "x"}
        )
        assert not r2.is_error
        assert (sandbox / "docs" / "new.txt").read_text() == "x"
        r3 = await conn.call_tool("list_directory", {"path": "docs"})
        assert "a.txt" in r3.content[0]["text"]
        assert "new.txt" in r3.content[0]["text"]
        r4 = await conn.call_tool("search_files", {"pattern": "**/*.md"})
        assert "docs/b.md" in r4.content[0]["text"]

    @pytest.mark.asyncio
    async def test_sandbox_escape_rejected(self, sandbox: Path) -> None:
        conn = FilesystemConnector(str(sandbox))
        r = await conn.call_tool("read_file", {"path": "../outside.txt"})
        assert r.is_error
        assert "outside sandbox" in r.content[0]["text"]
        r2 = await conn.call_tool("read_file", {"path": "/etc/passwd"})
        assert r2.is_error
        assert "outside sandbox" in r2.content[0]["text"]

    @pytest.mark.asyncio
    async def test_symlink_escape_rejected_for_read_write(
        self, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        (sandbox / "link").symlink_to(outside)
        conn = FilesystemConnector(str(sandbox))
        r = await conn.call_tool("read_file", {"path": "link"})
        assert r.is_error
        assert "outside sandbox" in r.content[0]["text"]
        w = await conn.call_tool("write_file", {"path": "link", "content": "nope"})
        assert w.is_error
        assert "outside sandbox" in w.content[0]["text"]
        assert outside.read_text() == "secret"

    @pytest.mark.asyncio
    async def test_search_excludes_symlinks_leaving_sandbox(
        self, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        (sandbox / "link").symlink_to(outside)
        conn = FilesystemConnector(str(sandbox))
        r = await conn.call_tool("search_files", {"pattern": "*"})
        assert "link" not in r.content[0]["text"]
        assert "docs/a.txt" in r.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_resources_skips_outbound_symlinks(
        self, sandbox: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        (sandbox / "out_link").symlink_to(outside)
        (sandbox / "in_link").symlink_to(sandbox / "docs" / "a.txt")
        conn = FilesystemConnector(str(sandbox))
        res = await conn.list_resources()
        names = [r["name"] for r in res]
        assert "out_link" not in names
        assert "in_link" in names
        assert "docs/a.txt" in names

    @pytest.mark.asyncio
    async def test_read_only_blocks_write_and_hides_tool(self, sandbox: Path) -> None:
        conn = FilesystemConnector(str(sandbox), read_only=True)
        r = await conn.call_tool("write_file", {"path": "x.txt", "content": "c"})
        assert r.is_error
        assert "read-only" in r.content[0]["text"]
        names = [t["name"] for t in await conn.list_tools()]
        assert "write_file" not in names

    @pytest.mark.asyncio
    async def test_file_too_large(self, sandbox: Path) -> None:
        (sandbox / "big.txt").write_bytes(b"x" * 100)
        conn = FilesystemConnector(str(sandbox), max_read_bytes=10)
        r = await conn.call_tool("read_file", {"path": "big.txt"})
        assert r.is_error
        assert "too large" in r.content[0]["text"]

    @pytest.mark.asyncio
    async def test_missing_file_and_not_a_file(self, sandbox: Path) -> None:
        conn = FilesystemConnector(str(sandbox))
        r = await conn.call_tool("read_file", {"path": "nope.txt"})
        assert r.is_error
        assert "not found" in r.content[0]["text"]
        r2 = await conn.call_tool("read_file", {"path": "docs"})
        assert r2.is_error
        assert "Not a file" in r2.content[0]["text"]

    @pytest.mark.asyncio
    async def test_list_directory_empty_and_missing(self, sandbox: Path) -> None:
        (sandbox / "empty").mkdir()
        conn = FilesystemConnector(str(sandbox))
        # Empty path means the sandbox root.
        assert (
            "[d] empty"
            in (await conn.call_tool("list_directory", {})).content[0]["text"]
        )
        r = await conn.call_tool("list_directory", {"path": "empty"})
        assert r.content[0]["text"] == "(empty)"
        r2 = await conn.call_tool("list_directory", {"path": "nope"})
        assert r2.is_error

    @pytest.mark.asyncio
    async def test_read_resource(self, sandbox: Path) -> None:
        conn = FilesystemConnector(str(sandbox))
        out = await conn.read_resource("file://docs/a.txt")
        assert out["contents"][0]["text"] == "alpha"
        assert out["contents"][0]["mimeType"] == "text/plain"
        out2 = await conn.read_resource("file://missing.txt")
        assert out2["contents"][0]["text"]  # error message surfaced as content

    @pytest.mark.asyncio
    async def test_unknown_tool(self, sandbox: Path) -> None:
        with pytest.raises(MCPToolCallError, match="Unknown filesystem tool"):
            await FilesystemConnector(str(sandbox)).call_tool("nope", {})
