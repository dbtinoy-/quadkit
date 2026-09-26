from __future__ import annotations

from pathlib import Path
import py_compile
import tempfile

from quadkit.events.cli.generators.query_handler import QueryHandlerGenerator


class TestQueryHandlerGenerator:
    def setup_method(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_generates_query_file(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("GetUser", fields_str="user_id:str")
        assert result.files_created == [self.tmp_dir / "get_user.py"]
        file_path = self.tmp_dir / "get_user.py"
        assert file_path.exists()

    def test_generated_file_is_valid_python(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("ListOrders")
        file_path = self.tmp_dir / "list_orders.py"
        py_compile.compile(file_path, doraise=True)

    def test_generated_content_has_query_classes(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("GetUser", fields_str="user_id:str")
        content = (self.tmp_dir / "get_user.py").read_text()
        assert "class GetUserQuery(Query):" in content
        assert "class GetUserHandler(" in content

    def test_dry_run_creates_no_files_on_disk(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("Widget", dry_run=True)
        assert result.files_created == [self.tmp_dir / "widget.py"]
        assert not (self.tmp_dir / "widget.py").exists()

    def test_files_skipped_on_existing_without_force(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item")
        assert result.files_skipped == [self.tmp_dir / "item.py"]
        assert result.files_created == []

    def test_force_overwrites_existing_file(self) -> None:
        gen = QueryHandlerGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item", force=True)
        assert result.files_overwritten == [self.tmp_dir / "item.py"]
