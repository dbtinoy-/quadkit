"""Staged-generation behavior tests for ServiceGenerator."""

from __future__ import annotations

from pathlib import Path

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
