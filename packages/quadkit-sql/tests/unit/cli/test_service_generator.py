"""Staged-generation behavior tests for ServiceGenerator."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from quadkit.sql.cli.generators import ServiceGenerator


def test_service_generator_renders_unit_of_work(tmp_path: Path) -> None:
    """The service generator emits a SimpleUnitOfWork-backed service."""
    gen = ServiceGenerator(output_dir=tmp_path)
    result = gen.generate("order", fields_str="email:str?")

    assert result.files_created == [tmp_path / "order_service.py"]
    content = (tmp_path / "order_service.py").read_text()
    assert "from quadkit.sql.unit_of_work import SimpleUnitOfWork" in content
    assert "class OrderService" in content
    assert "Controllers may" in content
    assert "does not automatically publish domain events" in content
    assert "domain events commit atomically" not in content
    # Create prepares the row (key + timestamps) before registering —
    # the tables' NOT NULL columns are not the caller's to name.
    assert "row = _prepare_new(data)" in content
    assert "uow.register_new(OrderEntity(**row))" in content
    assert "await uow.commit()" in content


def test_service_generator_dry_run_reports_without_writing(tmp_path: Path) -> None:
    """A dry run reports the target file without writing it."""
    gen = ServiceGenerator(output_dir=tmp_path)
    result = gen.generate("order", dry_run=True)

    assert not (tmp_path / "order_service.py").exists()
    assert (tmp_path / "order_service.py") in result.files_created


def test_every_public_method_returns_the_service_union(tmp_path: Path) -> None:
    """§5 law: expected domain outcomes are ``Result`` values on *every*
    public method — ``create``/``list`` included (uniform ``Ok`` keeps
    chains whole), with ``update`` present beside the other four."""
    gen = ServiceGenerator(output_dir=tmp_path)
    gen.generate("order", fields_str="email:str")

    content = (tmp_path / "order_service.py").read_text()
    assert (
        "from quadkit.contracts.exceptions import ConflictError, NotFoundError"
        in content
    )
    assert "from quadkit.result import Err, Ok, Result" in content
    # The standalone union signs the integrity arm inline: collisions
    # answer 409 ConflictError instead of escaping as 500s.
    for outcome in (
        "Result[dict[str, Any], ConflictError | NotFoundError]",
        "Result[list[dict[str, Any]], ConflictError | NotFoundError]",
        "Result[bool, ConflictError | NotFoundError]",
    ):
        assert outcome in content
    assert "except DuplicateKeyError:" in content
    assert "except ForeignKeyError:" in content  # restricted delete
    assert "_reference_error" not in content  # no FK fields on this entity
    for name in ("create", "get", "list", "update", "delete"):
        assert f"async def {name}(" in content
    # The §5 law binds public methods; the module-private row
    # preparation helper legitimately returns a plain dict.
    assert "-> dict[str, Any]:" not in content.replace(
        "def _to_dict", ""
    ).replace("def _prepare_new(data: dict[str, Any]) -> dict[str, Any]:", "")
    assert "return Ok(row)" in content
    assert "return Ok(result.rows)" in content
    assert "dict[str, Any] | None" not in content


def test_exception_and_union_are_context_options(tmp_path: Path) -> None:
    """A modular app declares its errors once: the service renders the
    module's own class and union alias, imported from its context root."""
    gen = ServiceGenerator(output_dir=tmp_path)
    gen.generate(
        "order",
        fields_str="email:str",
        not_found_error="OrderNotFoundError",
        service_error_union="OrderServiceError",
        exceptions_module="shop_api.modules.users.exceptions",
    )
    content = (tmp_path / "order_service.py").read_text()
    import_line = next(
        line
        for line in content.splitlines()
        if line.startswith("from shop_api.modules.users.exceptions import ")
    )
    assert import_line == (
        "from shop_api.modules.users.exceptions import "
        "OrderNotFoundError, OrderServiceError"
    )
    assert (
        "Result[dict[str, Any], OrderServiceError]" in content
    )
    assert "OrderNotFoundError(f" in content


def test_write_only_fields_are_stripped_from_returned_rows(tmp_path: Path) -> None:
    """A ``!writeonly`` field is writable but stripped from create/get/
    list/update returns via the public-row helper."""
    gen = ServiceGenerator(output_dir=tmp_path)
    gen.generate("account", fields_str="name:str,password_hash:str!writeonly")
    content = (tmp_path / "account_service.py").read_text()

    assert '_WRITE_ONLY_FIELDS = frozenset(["password_hash"])' in content
    assert "def _public_row(row: dict[str, Any]) -> dict[str, Any]:" in content
    assert "return Ok(_public_row(data))" in content
    assert "return Ok(_public_row(result.rows[0]))" in content
    assert "return Ok([_public_row(row) for row in result.rows])" in content


def test_validator_options_render_enforced_writes(tmp_path: Path) -> None:
    """The validator pair renders create/update enforcement before the
    unit-of-work write, and joins the service's error union."""
    gen = ServiceGenerator(output_dir=tmp_path)
    gen.generate(
        "order",
        fields_str="email:str",
        validator_module="validators.order",
        validator_function="validate_order_payload",
    )
    content = (tmp_path / "order_service.py").read_text()

    assert "from validators.order import validate_order_payload" in content
    assert content.count("problems = validate_order_payload(data)") == 2
    assert 'FieldError(field, message, code="validator_rule")' in content
    assert "ConflictError | ValidationError | NotFoundError" in content
    assert "FieldError, ValidationError" in content


def test_validator_options_must_come_as_a_pair(tmp_path: Path) -> None:
    """A half-named validator fails loudly instead of rendering unenforced."""
    gen = ServiceGenerator(output_dir=tmp_path)
    with pytest.raises(ValueError, match="must be passed together"):
        gen.generate("order", validator_module="validators.order")


def test_foreign_key_fields_render_reference_error_mapping(tmp_path: Path) -> None:
    """A structured FK field gives create/update a field-level 422 arm."""
    from quadkit.contracts.cli.parsers import EntitySpec, FieldSpec

    gen = ServiceGenerator(output_dir=tmp_path)
    gen.generate(
        "post",
        entity_spec=EntitySpec(
            name="post",
            table_name="posts",
            fields=(
                FieldSpec(
                    name="author_id",
                    type="uuid",
                    fk="authors.id",
                    on_delete="restrict",
                    indexed=True,
                ),
                FieldSpec(name="title", type="str"),
            ),
        ),
    )
    content = (tmp_path / "post_service.py").read_text()
    assert '"author_id": "authors.id"' in content
    assert 'code="reference_missing"' in content
    assert (
        "Result[dict[str, Any], ConflictError | ValidationError | NotFoundError]"
        in content
    )
    compile(content, "post_service.py", "exec")


def test_service_generator_output_passes_ruff(tmp_path: Path) -> None:
    """The rendered module survives ``ruff check`` in a fresh project tree.

    A generated app always ships ``[tool.ruff] src = ["src"]`` (the scaffold
    emits it), so ``<app>`` is first-party and its imports sit in the last
    group; isort correctness is a fact about that tree, not about the file
    alone, so the check has to run with the tree's own profile -- plain
    ``ruff check`` from the project root, never ``--isolated`` (which would
    classify first-party imports as third-party and demand a block layout no
    fresh QuadKit project actually uses).
    """
    (tmp_path / "pyproject.toml").write_text('[tool.ruff]\nsrc = ["src"]\n')
    src_shop = tmp_path / "src" / "shop"
    (src_shop / "services").mkdir(parents=True)
    (src_shop / "__init__.py").touch()
    gen = ServiceGenerator(output_dir=src_shop / "services")
    gen.generate("order", fields_str="email:str")
    target = src_shop / "services" / "order_service.py"

    ruff = shutil.which("ruff") or str(Path(sys.executable).with_name("ruff"))
    proc = subprocess.run(
        [ruff, "check", str(target)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
