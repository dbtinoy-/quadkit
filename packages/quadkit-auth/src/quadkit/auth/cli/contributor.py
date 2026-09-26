"""Auth CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    HookContribution,
    SchemaSetupContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "auth_guard",
        "Generate an authentication/authorization guard",
        "quadkit.auth.cli.generators.auth_guard:AuthGuardGenerator",
        "src/guards",
    ),
    (
        "auth_policy",
        "Generate an authorization policy",
        "quadkit.auth.cli.generators.auth_policy:AuthPolicyGenerator",
        "src/policies",
    ),
    (
        "guard",
        "Generate an authorization guard",
        "quadkit.auth.cli.generators.guard:AuthGuardGenerator",
        "src/guards",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="auth",
        category="auth",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class AuthCliContributor:
    """CLI contributor for the quadkit-auth package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "auth"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for auth."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `auth` command group."""
        return [
            CommandContribution(
                name="auth",
                help="Authentication and authorization management commands",
                app_factory_path="quadkit.auth.cli.commands:create_auth_app",
                contributor="auth",
                category="security",
                requires_app_context=True,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return auth service health check."""
        return [
            HealthCheckContribution(
                name="auth_service_status",
                description="Verify auth service and JWT manager are operational",
                check_path="quadkit.auth.cli.checks:check_auth_service",
                contributor="auth",
                category="security",
                timeout=5.0,
                critical=True,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return auth configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="jwt_secret_configured",
                description="Check JWT_SECRET env var or auth.jwt.secret config",
                check_path="quadkit.auth.cli.doctor:check_jwt_secret",
                contributor="auth",
                category="security",
            ),
            DoctorCheckContribution(
                name="auth_config_valid",
                description="Validate auth section in application.yaml",
                check_path="quadkit.auth.cli.doctor:check_auth_config",
                contributor="auth",
                category="security",
            ),
        ]

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return auth shell context."""
        return [
            ShellContextContribution(
                name="auth",
                description="AuthenticationService for interactive use",
                factory_path="quadkit.auth.cli.shell:provide_auth",
                contributor="auth",
            ),
        ]

    def get_hooks(self) -> list[HookContribution]:
        """Return auth lifecycle hooks."""
        return [
            HookContribution(
                event="post_command",
                handler_path="quadkit.auth.cli.hooks:log_auth_command",
                contributor="auth",
                priority=90,
            ),
        ]

    def get_schema_setup(self) -> list[SchemaSetupContribution]:
        """Return schema setup contributions for auth."""
        return [
            SchemaSetupContribution(
                name="auth.oauth_identities",
                description="OAuth identity linkage storage",
                setup_fn_path="quadkit.auth.cli.schema_setup:ensure_oauth_identities",
                contributor=self.contributor_id,
            ),
        ]


__all__ = ["AuthCliContributor"]
