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
    derived_index_name,
    foreign_key_constraint_name,
    pluralize_identifier,
)
from quadkit.contracts.cli.naming import to_camel_case, to_snake_case
from quadkit.contracts.cli.parsers import (
    EntitySpec,
    FieldSpec,
    IndexSpec,
    format_fields,
    parse_fields,
    resolve_field_specs,
)
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import (
    STRUCTURED_ENTITY_SPEC_CAPABILITY,
    GeneratorDefinition,
    GeneratorOption,
)

__all__ = [
    "STRUCTURED_ENTITY_SPEC_CAPABILITY",
    "CliContributorProtocol",
    "CommandContribution",
    "DoctorCheckContribution",
    "EntitySpec",
    "FieldSpec",
    "GenerationResult",
    "GeneratorDefinition",
    "GeneratorOption",
    "GeneratorProtocol",
    "HealthCheckContribution",
    "HookContribution",
    "IndexSpec",
    "ShellContextContribution",
    "derived_index_name",
    "foreign_key_constraint_name",
    "format_fields",
    "parse_fields",
    "pluralize_identifier",
    "resolve_field_specs",
    "to_camel_case",
    "to_snake_case",
]
