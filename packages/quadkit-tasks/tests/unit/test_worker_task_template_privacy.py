"""The generated task scaffold must not log returned job identifiers."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment


def test_generated_task_template_omits_job_id_from_logs() -> None:
    template_path = (
        Path(__file__).resolve().parents[2]
        / "src/quadkit/tasks/cli/templates/task.py.jinja2"
    )
    template = Environment().from_string(template_path.read_text())
    rendered = template.render(
        class_name="BatchExportTask",
        doc="",
        package_name="example",
        params=[],
        resource_name="batch_export",
        schedule="",
        task_name="batch-export",
    )

    assert 'logger.info("batch_export_dispatched")' in rendered
    assert "job_id=job_id" not in rendered
