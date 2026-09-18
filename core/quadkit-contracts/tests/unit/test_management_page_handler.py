"""Tests for ManagementPageHandler protocol (E5)."""

from __future__ import annotations

from quadkit.contracts.admin.page_handler import ManagementPageHandler


def test_handler_with_only_handle_satisfies_protocol() -> None:
    class BasicHandler:
        async def handle(self, request: object) -> object:
            return "response"

    assert isinstance(BasicHandler(), ManagementPageHandler)


def test_handler_with_handle_and_handle_action_satisfies_protocol() -> None:
    class FullHandler:
        async def handle(self, request: object) -> object:
            return "response"

        async def handle_action(self, request: object, action_name: str) -> object:
            return f"action:{action_name}"

    assert isinstance(FullHandler(), ManagementPageHandler)


def test_handle_action_is_duck_typed_not_required() -> None:
    class BasicHandler:
        async def handle(self, request: object) -> object:
            return "response"

    assert not hasattr(BasicHandler(), "handle_action")


def test_management_page_handler_exported_from_contracts_admin() -> None:
    from quadkit.contracts.admin import ManagementPageHandler as MH
    assert MH is ManagementPageHandler


def test_admin_page_handler_protocol_still_exported_for_compat() -> None:
    from quadkit.contracts.admin.page_handler import AdminPageHandlerProtocol
    assert AdminPageHandlerProtocol is ManagementPageHandler
