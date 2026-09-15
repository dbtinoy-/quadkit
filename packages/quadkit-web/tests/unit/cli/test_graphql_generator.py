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
