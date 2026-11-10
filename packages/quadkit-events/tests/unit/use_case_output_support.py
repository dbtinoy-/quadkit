"""Shared authored use-case fixtures; independent of pytest module names."""

import importlib.util
import sys

from quadkit.events.cli.generators.use_case import UseCaseGenerator


def generate(
    tmp_path, monkeypatch, outputs, fields_str="title:str", *, validate_inputs=True
):
    UseCaseGenerator(tmp_path).generate(
        "publish",
        fields_str=fields_str,
        spec={
            "typed_outcomes": True,
            "validate_inputs": validate_inputs,
            "writes": [{"field": "title", "source": "input.title"}],
            "output_fields": outputs,
        },
    )
    spec = importlib.util.spec_from_file_location(
        "output_example", tmp_path / "publish_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module
