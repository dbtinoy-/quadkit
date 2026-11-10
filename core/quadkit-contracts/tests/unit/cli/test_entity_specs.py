"""Structured entity contracts shared by CLI and Playground generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quadkit.contracts.cli import (
    STRUCTURED_ENTITY_SPEC_CAPABILITY,
    EntitySpec,
    FieldSpec,
    GeneratorDefinition,
    IndexSpec,
    derived_index_name,
    foreign_key_constraint_name,
    format_fields,
    parse_fields,
    pluralize_identifier,
    resolve_field_specs,
)


def test_pluralize_identifier_matches_shared_vectors() -> None:
    vectors = json.loads(
        (Path(__file__).with_name("pluralize_vectors.json")).read_text()
    )

    assert {source: pluralize_identifier(source) for source in vectors} == vectors


def test_field_string_is_an_exact_compatibility_spelling() -> None:
    fields = (
        FieldSpec(
            name="post_id",
            type="uuid",
            required=False,
            indexed=True,
            fk="posts.id",
            on_delete="set_null",
        ),
        FieldSpec(
            name="slug",
            type="str",
            unique=True,
            read_only=True,
            write_only=True,
            immutable=True,
            default="draft",
        ),
    )

    rendered = format_fields(fields)

    assert rendered == (
        "post_id:uuid?!indexed!fk=posts.id!ondelete=set_null,"
        "slug:str!unique!readonly!writeonly!immutable=draft"
    )
    assert tuple(parse_fields(rendered)) == fields
    assert (
        resolve_field_specs(rendered, EntitySpec("comment", "comments", fields))
        == fields
    )


def test_principal_assigned_round_trips_through_the_field_string() -> None:
    field = FieldSpec(name="author_subject", type="str", principal_assigned=True)

    rendered = format_fields((field,))

    assert rendered == "author_subject:str!principal"
    assert tuple(parse_fields(rendered)) == (field,)
    # The long spelling is an accepted alias for the same fact.
    assert tuple(parse_fields("author_subject:str!principal_assigned")) == (field,)
    # And it defaults off, so every pre-existing spelling is unchanged.
    assert FieldSpec(name="title", type="str").principal_assigned is False


@pytest.mark.parametrize("on_delete", ["cascade", "restrict", "set_null", "no_action"])
def test_parser_accepts_every_physical_on_delete_action(on_delete: str) -> None:
    field = parse_fields(f"post_id:uuid?!indexed!fk=posts.id!ondelete={on_delete}")[0]

    assert field.fk == "posts.id"
    assert field.on_delete == on_delete
    assert not field.required
    assert field.indexed


@pytest.mark.parametrize(
    "field",
    [
        "post_id:uuid!fk=Post",
        "post_id:uuid!fk=posts",
        "post_id:uuid!fk=.id",
        "post_id:uuid!fk=posts.",
        "post_id:uuid!ondelete=cascade",
        "post_id:uuid!fk=posts.id!ondelete=explode",
        # SET NULL on a required (NOT NULL) field can only fail at delete time.
        "post_id:uuid!fk=posts.id!ondelete=set_null",
    ],
)
def test_parser_rejects_ambiguous_or_invalid_foreign_keys(field: str) -> None:
    with pytest.raises(ValueError, match="Invalid field specification"):
        parse_fields(field)


def test_field_spec_rejects_set_null_on_a_required_field() -> None:
    with pytest.raises(ValueError, match="set_null requires an optional"):
        FieldSpec(
            name="post_id",
            type="uuid",
            fk="posts.id",
            on_delete="set_null",
        )


def test_entity_spec_validates_duplicate_fields_and_index_columns() -> None:
    with pytest.raises(ValueError, match="duplicates field"):
        EntitySpec(
            name="post",
            table_name="posts",
            fields=(
                FieldSpec(name="title", type="str"),
                FieldSpec(name="title", type="str"),
            ),
        )

    with pytest.raises(ValueError, match="unknown column"):
        EntitySpec(
            name="post",
            table_name="posts",
            fields=(FieldSpec(name="title", type="str"),),
            indexes=(IndexSpec(columns=("missing",)),),
        )


def test_resolve_field_specs_rejects_disagreement() -> None:
    spec = EntitySpec(
        name="post",
        table_name="posts",
        fields=(FieldSpec(name="title", type="str"),),
    )

    with pytest.raises(ValueError, match="disagree"):
        resolve_field_specs("title:text", spec)


def test_generated_constraint_and_index_names_are_capped_deterministically() -> None:
    long_table = "t" * 80
    long_column = "c" * 80

    fk_name = foreign_key_constraint_name(long_table, long_column, "targets")
    index_name = derived_index_name(long_table, (long_column,))

    assert len(fk_name) <= 60
    assert len(index_name) <= 60
    assert fk_name == foreign_key_constraint_name(long_table, long_column, "targets")
    assert index_name == derived_index_name(long_table, (long_column,))


def test_generator_definition_normalizes_capabilities() -> None:
    definition = GeneratorDefinition.make(
        "migration",
        description="Migration",
        generator_path="pkg.mod:MigrationGenerator",
        capabilities=[STRUCTURED_ENTITY_SPEC_CAPABILITY],
    )

    assert definition.capabilities == frozenset({STRUCTURED_ENTITY_SPEC_CAPABILITY})
    assert definition.supports(STRUCTURED_ENTITY_SPEC_CAPABILITY)
    assert not definition.supports("some_future_capability")


@pytest.mark.parametrize("text", ["title", b"title"])
def test_structured_specs_reject_text_instead_of_treating_it_as_a_collection(
    text: str | bytes,
) -> None:
    # Deliberately exercise untyped/plugin input at a typed constructor boundary.
    with pytest.raises(TypeError, match=r"IndexSpec\.columns must be an iterable"):
        IndexSpec(columns=text)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"EntitySpec\.fields must be an iterable"):
        EntitySpec(name="post", table_name="posts", fields=text)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"EntitySpec\.indexes must be an iterable"):
        EntitySpec(name="post", table_name="posts", fields=(), indexes=text)  # type: ignore[arg-type]


def test_structured_specs_keep_normalizing_nontext_iterables_to_tuples() -> None:
    field = FieldSpec(name="title", type="str")
    index = IndexSpec(columns=["title"])  # type: ignore[arg-type]
    entity = EntitySpec(
        name="post",
        table_name="posts",
        fields=[field],
        indexes=[index],  # type: ignore[arg-type]
    )
    assert index.columns == ("title",)
    assert entity.fields == (field,)
    assert entity.indexes == (index,)
