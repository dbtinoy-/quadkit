from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.codegen import parse_fields
from quadkit.codegen.base import GenerationResult, GeneratorBase


class DummyGenerator(GeneratorBase):
    def generate(self, name: str, **kwargs: object) -> GenerationResult:
        raise NotImplementedError


def test_parse_fields_preserves_constraints() -> None:
    fields = parse_fields(
        "email:str!unique,is_active:bool=false,team_id:int!fk=teams.id"
    )

    assert len(fields) == 3
    assert fields[0].name == "email"
    assert fields[0].type == "str"
    assert fields[0].unique is True
    assert fields[1].name == "is_active"
    assert fields[1].type == "bool"
    assert fields[1].default == "false"
    assert fields[2].name == "team_id"
    assert fields[2].type == "int"
    assert fields[2].fk == "teams.id"


def test_parse_fields_raises_for_malformed_segment() -> None:
    with pytest.raises(ValueError, match="Invalid field specification"):
        parse_fields("email:str,invalid")


def test_parse_fields_raises_for_invalid_constraint_suffix() -> None:
    with pytest.raises(ValueError, match="Invalid field specification"):
        parse_fields("email:str!unique!unknown")


def test_render_template_supports_jinja_syntax(tmp_path: Path) -> None:
    template_root = tmp_path / "templates"
    template_root.mkdir()
    (template_root / "example.py.jinja2").write_text(
        (
            "{% for field in fields %}{{ field.name | upper }}={{ field.type }}"
            "{% if not loop.last %}\n{% endif %}{% endfor %}\n"
        ),
        encoding="utf-8",
    )
    generator = DummyGenerator(output_dir=tmp_path / "src", template_root=template_root)

    rendered = generator.render_template(
        "example.py.jinja2",
        {
            "fields": [
                {"name": "email", "type": "str"},
                {"name": "age", "type": "int"},
            ]
        },
    )

    assert rendered == "EMAIL=str\nAGE=int\n"
