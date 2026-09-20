"""Tests for `quadkit gen controller` command."""

from __future__ import annotations

from typer.testing import CliRunner


class TestGenController:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_gen_controller_creates_file(
        self,
        temp_project,
        cli_app_with_web_generators,
    ) -> None:
        result = self.runner.invoke(
            cli_app_with_web_generators,
            [
                "gen",
                "controller",
                "Pet",
            ],
        )
        assert result.exit_code == 0
        created = temp_project / "src/test_project/controllers/pet_controller.py"
        # The console hard-wraps a long path mid-word, so compare with all
        # whitespace removed rather than on where rich broke the line.
        assert "".join(f"Created: {created}".split()) in "".join(
            result.output.split()
        )
        assert created.exists()

    def test_gen_controller_content(
        self,
        temp_project,
        cli_app_with_web_generators,
    ) -> None:
        result = self.runner.invoke(
            cli_app_with_web_generators,
            [
                "gen",
                "controller",
                "UserProfile",
            ],
        )
        assert result.exit_code == 0
        content = (
            temp_project / "src/test_project/controllers/user_profile_controller.py"
        ).read_text()
        assert "class UserProfileController(Controller):" in content
