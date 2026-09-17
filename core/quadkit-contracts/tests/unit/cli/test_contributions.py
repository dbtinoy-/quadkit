from quadkit.contracts.cli.contributions import (
    SchemaSetupContribution,
    SchemaSetupOutcome,
    SchemaSetupResult,
)


def test_schema_setup_result_values():
    assert SchemaSetupResult.CREATED == "created"
    assert SchemaSetupResult.ALREADY_PRESENT == "already_present"
    assert SchemaSetupResult.FAILED == "failed"


def test_schema_setup_outcome_defaults_no_message():
    outcome = SchemaSetupOutcome(status=SchemaSetupResult.CREATED)
    assert outcome.message is None


def test_schema_setup_outcome_carries_failure_message():
    outcome = SchemaSetupOutcome(status=SchemaSetupResult.FAILED, message="connection refused")
    assert outcome.status == SchemaSetupResult.FAILED
    assert outcome.message == "connection refused"


def test_schema_setup_contribution_fields():
    contribution = SchemaSetupContribution(
        name="example.tenant_configs",
        description="Tenant-scoped settings storage",
        setup_fn_path="example_app.schema_setup:ensure_tenant_configs",
        contributor="example",
    )
    assert contribution.name == "example.tenant_configs"
    assert contribution.category == "general"
