from quadkit.cli.contributors.runtime import ContributorRuntime
from quadkit.contracts.cli.contributions import SchemaSetupContribution


def test_schema_setups_aggregates_across_contributors():
    contribution = SchemaSetupContribution(
        name="example.tenant_configs",
        description="Tenant-scoped settings storage",
        setup_fn_path="example_app.schema_setup:ensure_tenant_configs",
        contributor="example",
    )

    class FakeContributor:
        def get_schema_setup(self) -> list[SchemaSetupContribution]:
            return [contribution]

    runtime = ContributorRuntime(contributors=[FakeContributor()])

    assert runtime.schema_setups == [contribution]


def test_schema_setups_empty_when_no_contributors_implement_it():
    class FakeContributor:
        pass

    runtime = ContributorRuntime(contributors=[FakeContributor()])

    assert runtime.schema_setups == []
