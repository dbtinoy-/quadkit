"""Web CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import DoctorCheckContribution
from quadkit.contracts.cli.types import GeneratorDefinition, GeneratorOption

_FIELDS_OPTION = GeneratorOption(
    name="fields",
    type_hint="str",
    description="Field spec in name:type[?][!unique][!fk=Model][=default] format",
)

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "controller",
        (
            "Generate a web controller with route handlers; imports the "
            "domains.<name> DTOs and repositories.<name>_repository class that "
            "`quadkit gen domain` and `quadkit gen repository` write"
        ),
        "quadkit.web.cli.generators.controller:ControllerGenerator",
        "src/controllers",
    ),
    (
        "resource",
        (
            "Generate a resource controller slice (the controller half; run "
            "`quadkit gen domain` and `quadkit gen repository` for the modules "
            "it imports)"
        ),
        "quadkit.web.cli.generators.resource:ResourceGenerator",
        "src",
    ),
    (
        "middleware",
        "Generate a web middleware component",
        "quadkit.web.cli.generators.middleware:MiddlewareGenerator",
        "src/middleware",
    ),
    (
        "graphql",
        "Generate a GraphQL schema and resolvers",
        "quadkit.web.cli.generators.graphql:GraphQLGenerator",
        "src/schema",
    ),
    (
        "webhook",
        "Generate a webhook handler",
        "quadkit.web.cli.generators.webhook:WebhookGenerator",
        "src/webhooks",
    ),
    (
        "websocket",
        "Generate a WebSocket handler",
        "quadkit.web.cli.generators.websocket:WebSocketHandlerGenerator",
        "src/websocket",
    ),
    (
        "exception_filter",
        "Generate a web exception filter",
        "quadkit.web.cli.generators.exception_filter:ExceptionFilterGenerator",
        "src/filters",
    ),
    (
        "interceptor",
        "Generate a web request/response interceptor",
        "quadkit.web.cli.generators.interceptor:InterceptorGenerator",
        "src/interceptors",
    ),
    (
        "error",
        "Generate a custom HTTP error",
        "quadkit.web.cli.generators.error:ErrorGenerator",
        "src/errors",
    ),
)

_OPTIONS: dict[str, tuple[GeneratorOption, ...]] = {
    "controller": (
        _FIELDS_OPTION,
        GeneratorOption(name="path", type_hint="str", description="Base API path"),
        GeneratorOption(name="doc", type_hint="str", description="Class docstring"),
    ),
    "resource": (_FIELDS_OPTION,),
    "exception_filter": (
        GeneratorOption(
            name="exception_type",
            type_hint="str",
            description="Exception class name the filter handles",
        ),
        GeneratorOption(
            name="status_code",
            type_hint="int",
            description="HTTP status code used in the default error response",
        ),
    ),
    "interceptor": (),
    "error": (
        GeneratorOption(
            name="status_code",
            type_hint="int",
            description="HTTP status code of the error",
        ),
        GeneratorOption(
            name="code",
            type_hint="str",
            description="Machine-readable error code",
        ),
        GeneratorOption(
            name="error_code",
            type_hint="str",
            description="Registry error code (QK_ERR_WEB_...)",
        ),
    ),
}

# Titles that make() cannot derive exactly.
_TITLES: dict[str, str] = {
    "graphql": "Generate GraphQL",
    "websocket": "Generate WebSocket",
}

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="web",
        category="web",
        options=_OPTIONS.get(name, ()),
        title=_TITLES.get(name),
    )
    for name, description, generator_path, output_dir in _SPECS
)


class WebCliContributor:
    """CLI contributor for the quadkit-web package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "web"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for web."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list:
        """Return no command contributions — web does not add command groups."""
        return []

    def get_health_checks(self) -> list:
        """Return no health check contributions."""
        return []

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return doctor checks for web route validation."""
        return [
            DoctorCheckContribution(
                name="web_routes_valid",
                description="Validate registered routes have valid controllers",
                check_path="quadkit.web.cli.checks:check_routes_valid",
                contributor="web",
                category="web",
            ),
        ]

    def get_shell_context(self) -> list:
        """Return no shell context contributions."""
        return []

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []


__all__ = ["WebCliContributor"]
