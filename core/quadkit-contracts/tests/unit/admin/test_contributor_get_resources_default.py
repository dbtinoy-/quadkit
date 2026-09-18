"""Tests for BaseAdminContributor.get_resources() default."""


def test_base_contributor_get_resources_defaults_empty() -> None:
    from quadkit.contracts.admin import BaseAdminContributor

    class C(BaseAdminContributor):
        name = "x"
        display_name = "X"
        group = "g"
        icon = "i"
        priority = 100
        version = "0"
        package_source = "p"
        required_permissions = frozenset()

    assert list(C().get_resources()) == []
