from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    HookContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.generators import (
    GenerationResult,
    GeneratorProtocol,
)
from quadkit.contracts.cli.naming import to_camel_case, to_snake_case
from quadkit.contracts.cli.parsers import FieldSpec, parse_fields
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition, GeneratorOption

__all__ = [
    "CliContributorProtocol",
    "CommandContribution",
    "DoctorCheckContribution",
    "FieldSpec",
    "GenerationResult",
    "GeneratorDefinition",
    "GeneratorOption",
    "GeneratorProtocol",
    "HealthCheckContribution",
    "HookContribution",
    "ShellContextContribution",
    "parse_fields",
    "to_camel_case",
    "to_snake_case",
]
