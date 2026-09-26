"""Contributor contract tests for the events CLI."""

from __future__ import annotations

from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.events.cli.contributor import EventsCliContributor
from quadkit.events.cli.generators.projection import ProjectionGenerator


def test_events_contributor_implements_protocol_shape() -> None:
    contributor = EventsCliContributor()

    assert isinstance(contributor, CliContributorProtocol)
    assert contributor.contributor_id == "events"


def test_events_contributor_exposes_expected_generators() -> None:
    contributor = EventsCliContributor()

    assert {definition.name for definition in contributor.get_generators()} == {
        "event_handler",
        "saga",
        "event",
        "command",
        "query",
        "projection",
    }


def test_events_contributor_paths_are_package_local() -> None:
    contributor = EventsCliContributor()

    assert {
        definition.generator_path for definition in contributor.get_generators()
    } == {
        "quadkit.events.cli.generators.event_handler:EventHandlerGenerator",
        "quadkit.events.cli.generators.saga:SagaGenerator",
        "quadkit.events.cli.generators.event_generator:EventGenerator",
        "quadkit.events.cli.generators.command_handler:CommandHandlerGenerator",
        "quadkit.events.cli.generators.query_handler:QueryHandlerGenerator",
        "quadkit.events.cli.generators.projection:ProjectionGenerator",
    }


def test_projection_generator_defaults() -> None:
    generator = ProjectionGenerator()

    assert generator.name == "projection"
    assert generator.default_output_dir == "src/projections"
    assert generator.description == "Generate an event projection for read models"
