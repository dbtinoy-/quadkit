"""Tests for the golden-tree generator assertion util."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.contracts.cli.generators import GenerationResult
from quadkit.testing.generators import assert_generated_tree


class ScriptedGenerator:
    def __init__(self, files: dict[str, str]) -> None:
        self._files = files

    def generate(self, name: str, **kwargs: object) -> GenerationResult:
        del name, kwargs
        created: list[Path] = []
        for rel, content in self._files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            created.append(target)
        return GenerationResult(files_created=created)

    root: Path


@pytest.fixture
def gen(tmp_path: Path) -> ScriptedGenerator:
    generator = ScriptedGenerator({"models/user.py": "class UserModel: ...\n"})
    generator.root = tmp_path / "out"
    generator.root.mkdir(parents=True)
    return generator


def test_passes_on_exact_tree(gen: ScriptedGenerator, tmp_path: Path) -> None:
    result = assert_generated_tree(
        gen,
        "user",
        root=tmp_path / "out",
        expected_files={"models/user.py": "class UserModel: ...\n"},
    )
    assert len(result.files_created) == 1


def test_fails_on_missing_file(gen: ScriptedGenerator, tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="missing files"):
        assert_generated_tree(
            gen,
            "user",
            root=tmp_path / "out",
            expected_files={
                "models/user.py": "class UserModel: ...\n",
                "services/user_service.py": "x",
            },
        )


def test_fails_on_extra_file(gen: ScriptedGenerator, tmp_path: Path) -> None:
    (tmp_path / "out" / "stray.txt").write_text("surprise")
    with pytest.raises(AssertionError, match="unexpected files"):
        assert_generated_tree(
            gen,
            "user",
            root=tmp_path / "out",
            expected_files={"models/user.py": "class UserModel: ...\n"},
        )


def test_fails_on_content_mismatch(gen: ScriptedGenerator, tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="Content mismatch"):
        assert_generated_tree(
            gen,
            "user",
            root=tmp_path / "out",
            expected_files={"models/user.py": "wrong content"},
        )
