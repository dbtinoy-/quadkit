"""Native atomic inbox emission is explicit and fails before writing files."""

from copy import deepcopy

import pytest

from quadkit.events.cli.generators.use_case import UseCaseGenerator

_BASE = {
    "atomic_transition": True,
    "principal_required": True,
    "validate_inputs": True,
    "typed_outcomes": True,
    "transition": {"field": "status", "from": "draft", "to": "published"},
    "writes": [{"field": "title", "source": "input.title"}],
    "inbox_notification": {"title": "Post published", "body_field": "title"},
}


@pytest.mark.parametrize(
    "option",
    [
        "atomic_transition",
        "principal_required",
        "validate_inputs",
        "typed_outcomes",
        "transition",
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_incomplete_context_refused_before_any_write(tmp_path, option, dry_run):
    spec = deepcopy(_BASE)
    spec[option] = False
    with pytest.raises(ValueError, match="requires"):
        UseCaseGenerator(tmp_path).generate(
            "publish", fields_str="title:str", spec=spec, dry_run=dry_run
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "value",
    [
        False,
        {},
        {"title": "Hi", "body_field": "title", "recipient": "spoof"},
        {"title": "", "body_field": "title"},
        {"title": "Hi", "body_field": "title.__class__"},
        {"title": "Hi", "body_field": "missing"},
        {"title": "\ud800", "body_field": "title"},
        {"title": "Hi", "body_field": "_private"},
    ],
)
def test_inbox_vocabulary_closed(tmp_path, value):
    spec = {**_BASE, "inbox_notification": value}
    with pytest.raises(ValueError, match="inbox_notification"):
        UseCaseGenerator(tmp_path).generate(
            "publish", fields_str="title:str", spec=spec
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "effect", ["stages", "enqueues", "related_reads", "counters", "custom_steps"]
)
def test_other_work_not_silently_composed(tmp_path, effect):
    with pytest.raises(ValueError, match="does not compose"):
        UseCaseGenerator(tmp_path).generate(
            "publish", fields_str="title:str", spec={**_BASE, effect: ["unsupported"]}
        )
    assert not list(tmp_path.iterdir())


def test_no_notification_dependency_without_explicit_opt_in(tmp_path):
    UseCaseGenerator(tmp_path).generate("publish", fields_str="title:str")
    assert "quadkit.notification" not in (tmp_path / "publish_use_case.py").read_text()
