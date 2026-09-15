from __future__ import annotations

from importlib.metadata import entry_points

from quadkit.cli.contributors.runtime import ENTRY_POINT_GROUP

_NON_SCOPE_WITH_ENTRY_POINT = {
    "admin",  # quadkit-admin — experimental tier, documented as non-scope
}


def _check_implements_protocol(obj: object) -> bool:
    return hasattr(obj, "contributor_id") and hasattr(obj, "get_generators")


def test_all_entry_points_load_successfully() -> None:
    eps = list(entry_points(group=ENTRY_POINT_GROUP))
    assert eps, "Expected at least the core CLI contributor"

    for ep in eps:
        cls = ep.load()
        instance = cls()
        assert _check_implements_protocol(instance), (
            f"{ep.name} does not satisfy CliContributorProtocol"
        )


def test_cli_runtime_does_not_import_extension_packages_directly() -> None:
    import ast
    from pathlib import Path

    cli_src = Path(__file__).parent.parent.parent / "src" / "quadkit" / "cli"
    forbidden_prefixes = {
        "quadkit.web",
        "quadkit.sql",
        "quadkit.auth",
        "quadkit.events",
        "quadkit.cache",
        "quadkit.ai",
    }

    py_files = list(cli_src.rglob("*.py"))
    assert py_files, f"No Python files found in {cli_src}"

    for py_file in py_files:
        if "templates" in str(py_file):
            continue
        source = py_file.read_text()
        if "from __future__" not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_prefixes:
                        assert not alias.name.startswith(forbidden), (
                            f"{py_file} imports {alias.name} (forbidden extension import)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module.startswith(f) for f in forbidden_prefixes
                ):
                    raise AssertionError(
                        f"{py_file} imports from {node.module} (forbidden extension import)"
                    )


def test_all_active_contributors_provide_contributor_id() -> None:
    runtime = _load_runtime()
    for contributor in runtime.contributors:
        assert contributor.contributor_id, (
            "Contributor must provide non-empty contributor_id"
        )


def _load_runtime():
    from quadkit.cli.contributors.runtime import ContributorRuntime

    return ContributorRuntime.from_entry_points()


def test_deploy_not_in_command_registry() -> None:
    from quadkit.cli.runtime.main import _BUILTIN_COMMANDS

    assert "deploy" not in _BUILTIN_COMMANDS
