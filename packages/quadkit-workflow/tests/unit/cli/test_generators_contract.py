"""Generator contract test for the workflow CLI contributor."""

from __future__ import annotations

from pathlib import Path

from quadkit.testing.generators_contract import (
    assert_contributor_generators_render,
)
from quadkit.workflow.cli.contributor import WorkflowCliContributor
from quadkit.workflow.cli.generators.pipeline import PipelineGenerator
from quadkit.workflow.cli.generators.saga_step import SagaStepGenerator


def test_all_generators_render(tmp_path: Path) -> None:
    """Every declared generator renders into tmp_path."""
    count = assert_contributor_generators_render(
        WorkflowCliContributor(), tmp_path=tmp_path
    )
    assert count >= 3


def test_generated_workflow_templates_do_not_log_names_or_identifiers(
    tmp_path: Path,
) -> None:
    """Generated scaffolds must not bind configured names into log records."""
    pipeline_dir = tmp_path / "pipelines"
    pipeline_result = PipelineGenerator(output_dir=pipeline_dir).generate(
        "PrivatePipelineSentinel"
    )
    pipeline_source = pipeline_result.files_created[0].read_text()
    assert 'logger.info("pipeline_stage_started")' in pipeline_source
    assert "pipeline=self.name" not in pipeline_source
    assert 'stage=getattr(stage, "__name__", str(stage))' not in pipeline_source

    saga_dir = tmp_path / "sagas"
    saga_result = SagaStepGenerator(output_dir=saga_dir).generate(
        "PrivateSagaStepSentinel"
    )
    saga_source = saga_result.files_created[0].read_text()
    assert 'logger.info("saga_step_executed")' in saga_source
    assert 'logger.warning("saga_step_compensated")' in saga_source
    assert "step=self.name" not in saga_source
