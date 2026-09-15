"""Tests for admin protocols."""

from __future__ import annotations

from quadkit.contracts.admin.protocols import AdminContributorProtocol


class TestAdminContributorProtocol:
    """Tests for AdminContributorProtocol."""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(AdminContributorProtocol, "__protocol_attrs__") or hasattr(AdminContributorProtocol, "__annotations__")

    def test_has_name_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "name")

    def test_has_display_name_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "display_name")

    def test_has_group_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "group")

    def test_has_icon_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "icon")

    def test_has_priority_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "priority")

    def test_has_package_source_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "package_source")

    def test_has_contributor_id_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "contributor_id")

    def test_has_required_permissions_property(self) -> None:
        assert hasattr(AdminContributorProtocol, "required_permissions")

    def test_has_get_dashboard_widgets_method(self) -> None:
        assert hasattr(AdminContributorProtocol, "get_dashboard_widgets")

    def test_has_get_navigation_items_method(self) -> None:
        assert hasattr(AdminContributorProtocol, "get_navigation_items")

    def test_has_get_management_pages_method(self) -> None:
        assert hasattr(AdminContributorProtocol, "get_management_pages")
