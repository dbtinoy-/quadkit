"""Generated payloads name types that exist (EVT-1).

The events templates render a field's type straight into a dataclass
annotation, and the field type arrives as free text from ``--fields``. That
works only while the token happens to be a builtin: ``order_id:uuid``,
``placed_at:datetime`` and ``payload:json`` all produced annotations no module
binds, so the generated file raised ``NameError`` on import — before pytest
could even collect it.

The fix has two halves that must agree, which is why they are tested
together: the annotation vocabulary and the imports that vocabulary needs. A
table of annotations without its import list just moves the NameError.

Each case generates into a real temporary package and **imports** the result,
because "the file parses" was already true of the broken output.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from quadkit.events.cli.generators.command_handler import CommandHandlerGenerator
from quadkit.events.cli.generators.event_generator import EventGenerator
from quadkit.events.cli.generators.query_handler import QueryHandlerGenerator
from quadkit.codegen import annotation_for, import_lines

#: One token per shape the bug had: a module name (``uuid``), a datetime name
#: (``datetime``/``date``), and a composite that needs a second import
#: (``json`` → ``dict[str, Any]``).
PAYLOAD = "order_id:uuid,total:decimal,placed_at:datetime,payload:json,day:date"


def _import_generated(path: Path, name: str, tmp_path: Path) -> object:
    sys.path.insert(0, str(tmp_path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        # dataclasses resolves annotations through ``sys.modules[__module__]``,
        # so the module has to be registered before it is executed.
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(tmp_path))
    return module


@pytest.mark.parametrize(
    ("generator", "name", "module_attr"),
    [
        (EventGenerator, "order_created", "OrderCreatedEvent"),
        (CommandHandlerGenerator, "place_order", "PlaceOrderCommand"),
        (QueryHandlerGenerator, "order_summary", "OrderSummaryQuery"),
    ],
)
def test_a_payload_with_module_level_types_imports(
    tmp_path: Path, generator: type, name: str, module_attr: str
) -> None:
    generated = generator(output_dir=tmp_path / name)
    generated.generate(name, fields_str=PAYLOAD, force=True)

    module = _import_generated(
        next((tmp_path / name).rglob("*.py")), f"generated_{name}", tmp_path
    )

    assert hasattr(module, module_attr)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("uuid", "UUID"),
        ("datetime", "datetime"),
        ("date", "date"),
        ("time", "time"),
        ("json", "dict[str, Any]"),
        ("decimal", "float"),
        ("str", "str"),
        ("int", "int"),
        # Unknown tokens degrade to themselves rather than blocking a
        # generation, the same stance the SQL vocabulary takes.
        ("something_odd", "something_odd"),
    ],
)
def test_the_annotation_vocabulary(token: str, expected: str) -> None:
    assert annotation_for(token) == expected


def test_composite_annotations_pull_in_their_second_name() -> None:
    """``dict[str, Any]`` needs ``Any``; the annotation alone is not enough."""
    assert import_lines(["json"]) == ["from typing import Any"]


def test_datetime_names_share_one_line_and_uuid_is_unconditional() -> None:
    lines = import_lines(["uuid", "datetime", "date"])

    assert lines == ["from datetime import date, datetime", "from uuid import UUID"]


def test_builtin_only_payloads_need_no_imports() -> None:
    assert import_lines(["str", "int", "float", "bool", "bytes"]) == []
