"""GraphQL generator regression tests."""

from __future__ import annotations

import ast
from pathlib import Path

from quadkit.web.cli.generators.graphql import GraphQLGenerator


def test_graphql_scaffold_has_executable_query_names(tmp_path: Path) -> None:
    """A plural resource name must not produce a double-plural field or NameError."""
    result = GraphQLGenerator(tmp_path).generate(
        "Invoice",
        fields_str="name:str,total:int",
    )
    content = Path(result.files_created[0]).read_text()

    ast.parse(content)
    assert "async def invoices(" in content
    assert "async def invoicess(" not in content
    assert "        invoices # TODO" not in content
    assert "from __future__ import annotations" in content


def test_graphql_scaffold_does_not_duplicate_timestamp_fields(tmp_path: Path) -> None:
    """Reserved timestamp columns must not be emitted twice on the GraphQL type."""
    result = GraphQLGenerator(tmp_path).generate(
        "Category",
        fields_str="created_at:datetime,active:bool",
    )
    content = Path(result.files_created[0]).read_text()

    tree = ast.parse(content)
    type_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "CategoryType"
    )
    fields = [
        node.target.id
        for node in type_node.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    ]
    assert fields.count("created_at") == 1
    assert fields.count("updated_at") == 1


def _load(path: Path, module_name: str) -> object:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_a_plural_resource_does_not_name_two_fields_alike(tmp_path: Path) -> None:
    """The list field and the by-id field must differ (GQL-1).

    ``singular_name`` was the input name, so ``quadkit gen graphql orders``
    emitted two ``async def orders`` in one class body: F811, and Strawberry
    then has one field where the generator meant two. The by-id field takes
    the singular form, which leaves singular inputs unchanged.
    """
    path = Path(GraphQLGenerator(tmp_path).generate("orders", fields_str="name:str").files_created[0])
    content = path.read_text()

    assert "async def orders(" in content
    assert "async def order(" in content
    assert content.count("async def orders(") == 1


def test_the_generated_schema_builds_with_both_query_fields(tmp_path: Path) -> None:
    """Importing and building the schema is the claim the entry was about.

    Pattern-matching cannot catch this class of defect: the module parses,
    and the failure only appears when Strawberry reads the class body.
    """
    import pytest

    pytest.importorskip("strawberry")
    import strawberry

    path = Path(
        GraphQLGenerator(tmp_path)
        .generate("orders", fields_str="name:str,amount:decimal")
        .files_created[0]
    )
    module = _load(path, "generated_graphql_orders")

    schema = strawberry.Schema(query=module.Query)
    sdl = str(schema)

    # The SDL is the contract a client reads: one list field and one by-id
    # field, under two different names.
    assert "orders(" in sdl
    assert "order(id: ID!): OrdersType" in sdl


def test_sibilant_names_pluralize_with_es(tmp_path: Path) -> None:
    """``box`` is queried as ``boxes``; ``boxs`` would be the field name."""
    path = Path(GraphQLGenerator(tmp_path).generate("box", fields_str="name:str").files_created[0])
    content = path.read_text()

    assert "async def boxes(" in content
    assert "async def box(" in content
    assert "boxs" not in content
