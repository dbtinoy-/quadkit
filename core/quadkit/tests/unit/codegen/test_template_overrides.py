"""Tests for user-owned stub override precedence in template resolution."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen.base import GeneratorBase
from quadkit.contracts.cli.generators import GenerationResult


class BareGenerator(GeneratorBase):
    def generate(self, name: str, **options: object) -> GenerationResult:
        raise NotImplementedError


def roots(
    tmp_path: Path,
    *,
    template_root: str | Path | None = None,
    module_name: str = "",
    fallbacks: list[Path] | None = None,
) -> list[Path]:
    return GeneratorBase._template_search_roots(
        template_root,
        project_anchor=tmp_path,
        module_name=module_name,
        package_fallbacks=fallbacks or [],
    )


class TestStubOverrideRoot:
    def test_derives_dotted_package_path_from_cli_module(self, tmp_path: Path) -> None:
        root = GeneratorBase._stub_override_root(
            "quadkit.web.cli.generators.controller", tmp_path
        )
        assert root == tmp_path / "stubs" / "quadkit" / "web"

    def test_isolates_packages(self, tmp_path: Path) -> None:
        web = GeneratorBase._stub_override_root(
            "quadkit.web.cli.generators.controller", tmp_path
        )
        sql = GeneratorBase._stub_override_root(
            "quadkit.sql.cli.generators.model", tmp_path
        )
        assert web != sql

    def test_none_without_anchor(self) -> None:
        assert (
            GeneratorBase._stub_override_root("quadkit.web.cli.generators.x", None)
            is None
        )

    def test_none_for_non_quadkit_module(self, tmp_path: Path) -> None:
        assert GeneratorBase._stub_override_root("pkg.gen.thing", tmp_path) is None


class TestSearchRootOrdering:
    def test_explicit_template_root_wins_over_everything(self, tmp_path: Path) -> None:
        explicit = tmp_path / "explicit"
        result = roots(
            tmp_path,
            template_root=explicit,
            module_name="quadkit.web.cli.generators.controller",
            fallbacks=[tmp_path / "pkg_templates"],
        )
        assert result[0] == explicit

    def test_stub_layer_sits_between_explicit_and_package(self, tmp_path: Path) -> None:
        result = roots(
            tmp_path,
            module_name="quadkit.web.cli.generators.controller",
            fallbacks=[tmp_path / "pkg_templates"],
        )
        assert result == [
            tmp_path / "stubs" / "quadkit" / "web",
            tmp_path / "pkg_templates",
        ]

    def test_no_override_layer_for_non_quadkit_module(self, tmp_path: Path) -> None:
        result = roots(
            tmp_path,
            module_name="other_pkg.generators.thing",
            fallbacks=[tmp_path / "pkg_templates"],
        )
        assert all("stubs" not in r.parts for r in result)


class TestResolveTemplateRootBehavior:
    def test_picks_first_existing_candidate(self, tmp_path: Path, monkeypatch) -> None:
        pkg_templates = tmp_path / "pkg" / "templates"
        pkg_templates.mkdir(parents=True)

        def fake_roots(cls, tr, **kw) -> list[Path]:
            return [tmp_path / "missing", pkg_templates]

        monkeypatch.setattr(
            BareGenerator, "_template_search_roots", classmethod(fake_roots)
        )
        gen = BareGenerator(output_dir=tmp_path / "out")
        assert gen.template_root == pkg_templates

    def test_last_candidate_returned_when_none_exist(self, tmp_path: Path) -> None:
        gen = BareGenerator(output_dir=tmp_path / "out")
        assert isinstance(gen.template_root, Path)

    def test_existing_stubs_dir_wins_for_quadkit_module(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import sys
        import types

        stubs = tmp_path / "stubs" / "quadkit" / "web"
        stubs.mkdir(parents=True)

        def fake_anchor(start):  # noqa: ARG001
            return tmp_path

        monkeypatch.setattr("quadkit.codegen.base.find_project_anchor", fake_anchor)

        holder = tmp_path / "controller.py"
        holder.write_text("", encoding="utf-8")
        fake_module = types.ModuleType("quadkit.web.cli.generators.controller")
        fake_module.__file__ = str(holder)
        monkeypatch.setitem(
            sys.modules, "quadkit.web.cli.generators.controller", fake_module
        )

        FakeWebGenerator = type("FakeWebGenerator", (GeneratorBase,), {})
        FakeWebGenerator.__module__ = "quadkit.web.cli.generators.controller"  # type: ignore[misc]
        gen = FakeWebGenerator(output_dir=tmp_path / "out")

        assert gen.template_root == stubs
