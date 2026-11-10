"""One native composition root: SQL, signed auth, queue and Web controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from notification_center.trusted.controller import TrustedPublicationController
from notification_center.trusted.service import TrustedPublication
from quadkit.app.base import Application
from quadkit.config import BaseConfig, QuadkitConfig
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.di.provider import Provider
from quadkit.sql.module import DatabaseModule
from quadkit.validation import Field, SecretStr
from quadkit.web.module import WebModule

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


@dataclass(init=False)
class TrustedPublicationConfig(BaseConfig):
    """Deployment-owned routing/signing settings, never request fields."""

    config_section: ClassVar[str] = "trusted_publication"
    recipient_email: str = Field(min_length=1)
    token_secret: SecretStr = Field(min_length=32)


class TrustedPublicationProvider(Provider):
    """Initialize committed schema before controllers or CLI can use the service."""

    name = "trusted_publication"
    config_key = "trusted_publication"
    config_model = TrustedPublicationConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Declare the service's native SQL and typed configuration dependencies."""
        if not isinstance(self.config, TrustedPublicationConfig):
            raise TypeError("Trusted publication configuration is required")
        settings = self.config

        async def build(resolver: ContainerResolverProtocol) -> TrustedPublication:
            return TrustedPublication(
                await resolver.resolve(DatabaseProviderProtocol),
                settings.recipient_email,
                settings.token_secret,
            )

        container.singleton(TrustedPublication, build)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Bootstrap once, outside any business transaction."""
        service = await container.resolve(TrustedPublication)
        await service.initialize()


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Compose native modules; normal Notification Center mode is unchanged."""
    app = Application(name="editorial-notifications", config=config)
    app.add_modules(
        [
            DatabaseModule.configure(),
            WebModule.configure(controllers=[TrustedPublicationController]),
        ]
    )
    app.add_providers([TrustedPublicationProvider()])
    return app
