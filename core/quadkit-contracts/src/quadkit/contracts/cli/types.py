from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

#: Capability declared by generators that accept a structured
#: ``quadkit.contracts.cli.parsers.EntitySpec`` instead of requiring entity
#: metadata to be flattened through the legacy ``fields_str`` syntax.
STRUCTURED_ENTITY_SPEC_CAPABILITY = "structured_entity_spec_v1"


@dataclass(frozen=True)
class GeneratorOption:
    """A single CLI option/flag accepted by a generator command.

    Used for auto-generated help text and input validation.
    """

    name: str
    type_hint: str  # e.g. "str", "bool", "int"
    required: bool = False
    default: object | None = None
    description: str = ""
    short_flag: str | None = None  # e.g. "-n"


@dataclass(frozen=True)
class GeneratorDefinition:
    """Describes a single executable scaffolding generator contributed to the CLI.

    Generators are discovered via ``CliContributorProtocol.get_generators()``
    and assembled into the unified ``gen`` command by ``CommandAssembler``.
    ``generator_path`` is required so every definition can be executed once it
    has been discovered and registered.
    """

    name: str
    title: str
    description: str
    contributor: str  # contributor_id of the owning contributor
    generator_path: str
    category: str = "general"
    options: tuple[GeneratorOption, ...] = field(default_factory=tuple)
    default_output_dir: str = "src"
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))

    def supports(self, capability: str) -> bool:
        """Whether this generator declares *capability*.

        Discovery must be declarative: bridges should not probe a generator
        by calling it with structured input and interpreting a ``TypeError``
        after files may already have been staged.
        """

        return capability in self.capabilities

    @classmethod
    def make(
        cls,
        name: str,
        *,
        description: str,
        generator_path: str,
        output_dir: str = "src",
        contributor: str = "",
        category: str = "general",
        options: tuple[GeneratorOption, ...] = (),
        title: str | None = None,
        capabilities: Iterable[str] = (),
    ) -> GeneratorDefinition:
        """Build a definition with conventional title derivation.

        The title defaults to ``"Generate <Title Case Of Name>"`` — e.g.
        ``auth_guard`` becomes ``Generate Auth Guard``. Pass ``title`` to
        override for names where the derivation reads poorly.

        Args:
            name: Snake_case generator identifier (also the CLI command name).
            description: One-line description shown in help text.
            generator_path: Import path ``"pkg.module:ClassName"`` of the
                generator implementation.
            output_dir: Default output directory relative to the project root.
            contributor: ``contributor_id`` of the owning contributor.
            category: Grouping bucket used by interactive listings.
            options: Typed CLI options accepted by the generator.
            title: Explicit human-readable title overriding the derivation.
            capabilities: Declarative generator capabilities bridges may
                require before invoking the generator.

        Returns:
            A frozen :class:`GeneratorDefinition`.
        """
        derived_title = title or (
            "Generate "
            + " ".join(w.capitalize() for w in name.replace("-", "_").split("_"))
        )
        return cls(
            name=name,
            title=derived_title,
            description=description,
            contributor=contributor,
            generator_path=generator_path,
            category=category,
            options=options,
            default_output_dir=output_dir,
            capabilities=frozenset(capabilities),
        )


__all__ = [
    "STRUCTURED_ENTITY_SPEC_CAPABILITY",
    "GeneratorDefinition",
    "GeneratorOption",
]
