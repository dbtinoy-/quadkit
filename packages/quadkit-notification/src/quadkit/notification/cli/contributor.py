"""Notification CLI contributor definitions."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    SchemaSetupContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "notification_template",
        "Generate a notification template",
        "quadkit.notification.cli.generators.template:NotificationTemplateGenerator",
        "src/notifications",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="notification",
        category="notification",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class NotificationCliContributor:
    """CLI contributor for the quadkit-notification package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "notification"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for notification."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `notify` command group."""
        return [
            CommandContribution(
                name="notify",
                help="Notification channel management commands",
                app_factory_path="quadkit.notification.cli.commands:create_notify_app",
                contributor="notification",
                category="notification",
                requires_app_context=True,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return notification channel health checks."""
        return [
            HealthCheckContribution(
                name="notification_channels",
                description="Check notification channels are reachable",
                check_path="quadkit.notification.cli.checks:check_notification_channels",
                contributor="notification",
                category="notification",
                timeout=15.0,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return notification configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="smtp_configured",
                description="Check SMTP configuration is present",
                check_path="quadkit.notification.cli.doctor:check_smtp_config",
                contributor="notification",
                category="notification",
            ),
            DoctorCheckContribution(
                name="push_credentials_configured",
                description="Check push notification credentials are configured",
                check_path="quadkit.notification.cli.doctor:check_push_credentials",
                contributor="notification",
                category="notification",
            ),
        ]

    def get_shell_context(self) -> list[Any]:
        """Return no shell context contributions."""
        return []

    def get_hooks(self) -> list[Any]:
        """Return no hook contributions."""
        return []

    def get_schema_setup(self) -> list[SchemaSetupContribution]:
        """Return schema setup contributions for notification."""
        return [
            SchemaSetupContribution(
                name="notification.inbox_messages",
                description="In-app notification inbox storage",
                setup_fn_path="quadkit.notification.cli.schema_setup:ensure_inbox_messages",
                contributor=self.contributor_id,
            ),
        ]


__all__ = ["NotificationCliContributor"]
