"""Staged-generation behavior tests for ServiceGenerator."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from quadkit.sql.cli.generators import ServiceGenerator


def test_service_generator_renders_unit_of_work(tmp_path: Path) -> None:
    """The service generator emits a SimpleUnitOfWork-backed service."""
    gen = ServiceGenerator(output_dir=tmp_path)
    result = gen.generate("order", fields_str="email:str?")

    assert result.files_created == [tmp_path / "order_service.py"]
    content = (tmp_path / "order_service.py").read_text()
    assert "from quadkit.sql.unit_of_work import SimpleUnitOfWork" in content
    assert "class OrderService" in content
    assert "uow.register_new(OrderEntity(**data))" in content
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
    assert "from quadkit.contracts.exceptions import NotFoundError" in content
    assert "from quadkit.result import Err, Ok, Result" in content
    union = "Result[%s, NotFoundError]"
    for outcome in (
        "Result[dict[str, Any], NotFoundError]",
        "Result[list[dict[str, Any]], NotFoundError]",
        "Result[bool, NotFoundError]",
    ):
        assert outcome in content
    for name in ("create", "get", "list", "update", "delete"):
        assert f"async def {name}(" in content
    assert "-> dict[str, Any]:" not in content.replace(
        "def _to_dict", ""
    )
    assert "return Ok(data)" in content
    assert "return Ok(result.rows)" in content
    assert "dict[str, Any] | None" not in content
    del union


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
