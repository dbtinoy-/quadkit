from __future__ import annotations

import pathlib
import tomllib

import pytest

from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.web.cli.contributor import WebCliContributor
from quadkit.web.cli.generators.controller import ControllerGenerator
from quadkit.web.cli.generators.error import ErrorGenerator
from quadkit.web.cli.generators.exception_filter import ExceptionFilterGenerator
from quadkit.web.cli.generators.interceptor import InterceptorGenerator
from quadkit.web.cli.generators.resource import ResourceGenerator


def test_web_contributor_implements_protocol_shape() -> None:
    contributor = WebCliContributor()

    assert isinstance(contributor, CliContributorProtocol)
    assert contributor.contributor_id == "web"


def test_web_contributor_exposes_expected_generators() -> None:
    contributor = WebCliContributor()

    assert {definition.name for definition in contributor.get_generators()} == {
        "controller",
        "resource",
        "middleware",
        "graphql",
        "webhook",
        "websocket",
        "exception_filter",
        "interceptor",
        "error",
    }


def test_web_contributor_paths_are_package_local() -> None:
    contributor = WebCliContributor()

    assert {
        definition.generator_path for definition in contributor.get_generators()
    } == {
        "quadkit.web.cli.generators.controller:ControllerGenerator",
        "quadkit.web.cli.generators.resource:ResourceGenerator",
        "quadkit.web.cli.generators.middleware:MiddlewareGenerator",
        "quadkit.web.cli.generators.graphql:GraphQLGenerator",
        "quadkit.web.cli.generators.webhook:WebhookGenerator",
        "quadkit.web.cli.generators.websocket:WebSocketHandlerGenerator",
        "quadkit.web.cli.generators.exception_filter:ExceptionFilterGenerator",
        "quadkit.web.cli.generators.interceptor:InterceptorGenerator",
        "quadkit.web.cli.generators.error:ErrorGenerator",
    }


def test_web_pyproject_declares_cli_contributor_entry_point() -> None:
    pyproject_path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text())
    group = data["project"]["entry-points"]["quadkit.cli.contributors"]

    assert group["web"] == "quadkit.web.cli.contributor:WebCliContributor"


def test_exception_filter_generator_defaults() -> None:
    generator = ExceptionFilterGenerator()

    assert generator.name == "exception_filter"
    assert generator.default_output_dir == "src/filters"


def test_interceptor_generator_defaults() -> None:
    generator = InterceptorGenerator()

    assert generator.name == "interceptor"
    assert generator.default_output_dir == "src/interceptors"


def test_error_generator_defaults() -> None:
    generator = ErrorGenerator()

    assert generator.name == "error"
    assert generator.default_output_dir == "src/errors"


def test_resource_generator_uses_package_local_controller() -> None:
    generator = ResourceGenerator()

    assert generator.controller_generator_class is ControllerGenerator


@pytest.mark.parametrize(
    ("name", "default_output_dir"),
    [
        ("controller", "src/controllers"),
        ("resource", "src"),
        ("middleware", "src/middleware"),
        ("graphql", "src/schema"),
        ("webhook", "src/webhooks"),
        ("websocket", "src/websocket"),
        ("exception_filter", "src/filters"),
        ("interceptor", "src/interceptors"),
        ("error", "src/errors"),
    ],
)
def test_web_generator_defaults(name: str, default_output_dir: str) -> None:
    contributor = WebCliContributor()
    definitions = {
        definition.name: definition for definition in contributor.get_generators()
    }

    assert definitions[name].default_output_dir == default_output_dir
    assert definitions[name].contributor == "web"
    assert definitions[name].category == "web"
