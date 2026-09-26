from __future__ import annotations

from pathlib import Path
import py_compile
import tempfile

from quadkit.auth.cli.generators.guard import AuthGuardGenerator


class TestGuardGenerator:
    def setup_method(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())

    def test_generates_guard_file(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        result = gen.generate("AdminOnly")
        assert len(result.files_created) == 1
        file_path = self.tmp_dir / "admin_only_guard.py"
        assert file_path.exists()

    def test_generated_file_is_valid_python(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        gen.generate("RoleBased")
        file_path = self.tmp_dir / "role_based_guard.py"
        py_compile.compile(file_path, doraise=True)

    def test_generated_content_has_guard_class(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        gen.generate("AdminOnly")
        content = (self.tmp_dir / "admin_only_guard.py").read_text()
        assert "AdminOnly" in content or "AdminOnlyGuard" in content
        assert "Guard" in content

    def test_dry_run_creates_no_files(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Widget", dry_run=True)
        assert not (self.tmp_dir / "widget_guard.py").exists()

    def test_files_skipped_on_existing_without_force(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        gen.generate("Item")
        result = gen.generate("Item")
        assert len(result.files_created) == 0

    def test_guard_type_role(self) -> None:
        gen = AuthGuardGenerator(output_dir=str(self.tmp_dir))
        gen.generate("AdminOnly", type="role")
        content = (self.tmp_dir / "admin_only_guard.py").read_text()
        assert "RoleGuard" in content or "role" in content.lower()
