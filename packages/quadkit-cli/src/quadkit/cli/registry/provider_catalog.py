"""Provider catalog for the add command.

Defines the provider value type and the built-in provider classes that
describe each installable Quadkit package and its default config.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ProviderInfo:
    """Information about a Quadkit provider."""

    name: str
    package: str
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    optional_dependencies: list[str] = field(default_factory=list)


class Provider(abc.ABC):
    """Abstract base class for providers."""

    name: ClassVar[str]
    package: ClassVar[str]
    description: ClassVar[str]
    config: ClassVar[dict[str, Any]] = {}

    @abc.abstractmethod
    def get_info(self) -> ProviderInfo:
        """Get provider information."""


class DatabaseService(Provider):
    """Database provider."""

    name = "database"
    package = "quadkit-sql"
    description = "Database ORM and migrations"
    config = {
        "database": {
            "url": "sqlite:///./dev.db",
            "echo": False,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class AuthProvider(Provider):
    """Authentication provider."""

    name = "auth"
    package = "quadkit-auth"
    description = "Authentication and authorization"
    config = {
        "auth": {
            "secret": "your-secure-secret-key-here",
            "algorithm": "HS256",
            "expire_minutes": 60,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class AIProvider(Provider):
    """AI/LLM provider."""

    name = "ai"
    package = "quadkit-ai"
    description = "AI and LLM integration"
    config = {
        "ai": {
            "provider": "ollama",
            "model": "llama3",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class CacheProvider(Provider):
    """Caching provider."""

    name = "cache"
    package = "quadkit-cache"
    description = "Caching layer"
    config = {
        "cache": {
            "backend": "memory",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class QueueProvider(Provider):
    """Queue/broker provider."""

    name = "queue"
    package = "quadkit-queue"
    description = "Message broker and queues"
    config = {
        "queue": {
            "broker": "redis",
            "url": "redis://localhost:6379/0",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class MessagingProvider(Provider):
    """Messaging provider (notifications + email)."""

    name = "messaging"
    package = "quadkit-notification"
    description = "Email and notification delivery"
    config = {
        "notification": {
            "backend": "smtp",
            "from_email": "noreply@example.com",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class NotificationProvider(Provider):
    """Notification provider."""

    name = "notification"
    package = "quadkit-notification"
    description = "SMS + push notifications"
    config = {
        "notification": {
            "sms_backend": "twilio",
            "push_backend": "fcm",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class EventsProvider(Provider):
    """Events provider."""

    name = "events"
    package = "quadkit-events"
    description = "Event handling and dispatch"
    config = {
        "events": {
            "store": "postgres",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class SearchProvider(Provider):
    """Search provider."""

    name = "search"
    package = "quadkit-search"
    description = "Full-text search"
    config = {
        "search": {
            "backend": "elasticsearch",
            "url": "http://localhost:9200",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class StorageProvider(Provider):
    """Storage provider."""

    name = "storage"
    package = "quadkit-storage"
    description = "File storage"
    config = {
        "storage": {
            "driver": "local",
            "root": "./storage",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class MonitorProvider(Provider):
    """Monitoring provider."""

    name = "monitor"
    package = "quadkit-monitor"
    description = "Monitoring and observability"
    config = {
        "monitor": {
            "enabled": True,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class TasksProvider(Provider):
    """Background tasks provider."""

    name = "tasks"
    package = "quadkit-tasks"
    description = "Background task processing"
    config = {
        "tasks": {
            "worker": "celery",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class GraphQLProvider(Provider):
    """GraphQL provider."""

    name = "graphql"
    package = "quadkit-graphql"
    description = "GraphQL API support"
    config = {
        "graphql": {
            "path": "/graphql",
            "graphiql": True,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class ResilienceProvider(Provider):
    """Resilience patterns provider.

    Resilience is now part of the core *quadkit* package; the provider
    exists primarily for configuration metadata rather than pulling in an
    external distribution.
    """

    name = "resilience"
    package = "quadkit"  # core quadkit package contains resilience
    description = "Resilience and fault tolerance"
    config = {
        "resilience": {
            "timeout": 30,
            "retry_count": 3,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class MonitoringProvider(Provider):
    """Monitoring and observability provider."""

    name = "monitoring"
    package = "quadkit-monitoring"
    description = "Monitoring and observability"
    config = {
        "monitoring": {
            "service_name": "my-app",
            "otel": {
                "enabled": True,
                "exporter": "otlp",
            },
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class WebProvider(Provider):
    """Web framework provider."""

    name = "web"
    package = "quadkit-web"
    description = "Web framework"
    config = {
        "web": {
            "host": "0.0.0.0",  # noqa: S104 — provider config template default
            "port": 8000,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class AdminProvider(Provider):
    """Admin panel provider."""

    name = "admin"
    package = "quadkit-admin"
    description = "Admin panel"
    config = {
        "admin": {
            "path": "/admin",
            "theme": "dark",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class ConnectProvider(Provider):
    """External connections provider."""

    name = "http"
    package = "quadkit"
    description = "HTTP client (built into quadkit core)"
    config = {
        "connect": {
            "base_url": "http://localhost:8080",
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class CommonProvider(Provider):
    """Common utilities provider."""

    name = "common"
    package = "quadkit-common"
    description = "Core utilities"
    config = {
        "common": {
            "logging": {"level": "INFO"},
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )


class TestingProvider(Provider):
    """Testing utilities provider."""

    name = "testing"
    package = "quadkit-testing"
    description = "Testing utilities"
    config = {
        "testing": {
            "db_reuse": True,
        },
    }

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name=self.name,
            package=self.package,
            description=self.description,
            config=self.config,
        )
