"""TokenExtractor sources: Authorization, X-Qk-Erp-Token, query, cookie."""

from __future__ import annotations

from quadkit.auth.web.middleware.token_extractor import TokenExtractor


class _Config:
    header_name = "Authorization"
    scheme = "Bearer"


class _Request:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.cookies = cookies or {}


def test_extracts_bearer_authorization() -> None:
    token = TokenExtractor(_Config()).extract_token(
        _Request(headers={"Authorization": "Bearer jwt-1"})
    )
    assert token == "jwt-1"


def test_extracts_qk_erp_header_when_authorization_is_absent() -> None:
    token = TokenExtractor(_Config()).extract_token(
        _Request(headers={"X-Qk-Erp-Token": "jwt-from-proxy"})
    )
    assert token == "jwt-from-proxy"


def test_authorization_wins_over_qk_erp_header() -> None:
    token = TokenExtractor(_Config()).extract_token(
        _Request(
            headers={
                "Authorization": "Bearer jwt-auth",
                "X-Qk-Erp-Token": "jwt-other",
            }
        )
    )
    assert token == "jwt-auth"


def test_bare_qk_erp_header_is_accepted() -> None:
    token = TokenExtractor(_Config()).extract_token(
        _Request(headers={"X-Qk-Erp-Token": "qke_machine_key"})
    )
    assert token == "qke_machine_key"


def test_no_part_of_a_credential_reaches_the_log(caplog) -> None:
    """Presence is logged at debug; the token — not even a prefix — never is."""
    import logging

    with caplog.at_level(logging.DEBUG):
        token = TokenExtractor(_Config()).extract_token(
            _Request(
                headers={"Authorization": "Bearer qke_SUPERSECRETVALUE_1234567890"}
            )
        )
    assert token == "qke_SUPERSECRETVALUE_1234567890"
    assert "SUPERSECRET" not in caplog.text
    assert "qke_SUPERS" not in caplog.text
    assert all(
        record.levelno <= logging.DEBUG
        for record in caplog.records
        if "TokenExtractor" in record.getMessage()
    )


def test_authorization_scheme_matches_case_insensitively_with_ascii_spaces() -> None:
    extractor = TokenExtractor(_Config())
    for scheme in ("Bearer", "bearer", "BEARER", "bEaReR"):
        for spaces in (" ", "  ", "   "):
            token = extractor.extract_token(
                _Request(headers={"Authorization": f"{scheme}{spaces}jwt-1"})
            )
            assert token == "jwt-1"


def test_bearer_normalization_does_not_remove_token_trailing_whitespace() -> None:
    extractor = TokenExtractor(_Config())
    assert (
        extractor.extract_token(_Request(headers={"Authorization": "bearer  jwt-1 "}))
        == "jwt-1 "
    )


def test_bearer_change_preserves_legacy_sources_and_tab_behavior() -> None:
    extractor = TokenExtractor(_Config())
    assert (
        extractor.extract_token(_Request(headers={"Authorization": "bare.token"}))
        == "bare.token"
    )
    assert (
        extractor.extract_token(_Request(headers={"X-Qk-Erp-Token": "machine"}))
        == "machine"
    )
    assert extractor.extract_token(_Request(query_params={"token": "query"})) == "query"
    assert (
        extractor.extract_token(_Request(cookies={"access_token": "cookie"}))
        == "cookie"
    )
    # A tab is not an ASCII space: legacy bare-token fallback is preserved.
    assert (
        extractor.extract_token(_Request(headers={"Authorization": "bearer\tjwt"}))
        == "bearer\tjwt"
    )
