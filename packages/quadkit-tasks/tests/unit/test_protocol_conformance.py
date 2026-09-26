"""Protocol conformance tests for quadkit-tasks domain models.

Verifies that the concrete JobProtocol and JobTemplateProtocol dataclasses satisfy
the runtime-checkable protocols defined in quadkit-contracts.
"""

from quadkit.contracts.infra.tasks import JobProtocol as JobProtocol
from quadkit.contracts.infra.tasks import JobTemplateProtocol as JobTemplateProtocol
from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.scheduling.templates import JobTemplateProtocol


class TestJobProtocolConformance:
    """Verify JobProtocol dataclass satisfies the contracts JobProtocol protocol."""

    def test_job_is_instance_of_job_protocol(self) -> None:
        """A concrete JobProtocol must satisfy the @runtime_checkable JobProtocol."""
        job = JobProtocol(id="test-id", name="my_task")

        assert isinstance(
            job,
            JobProtocol,
        ), "JobProtocol dataclass must be an instance of quadkit.contracts.tasks.JobProtocol protocol"

    def test_job_has_all_required_protocol_fields(self) -> None:
        """Each field declared on the JobProtocol must exist on a JobProtocol instance."""
        job = JobProtocol(id="test-id", name="my_task")

        required_fields = ("id", "name", "args", "kwargs", "priority", "status", "max_retries", "timeout")
        for field_name in required_fields:
            assert hasattr(job, field_name), f"JobProtocol is missing protocol field: {field_name!r}"


class TestJobTemplateProtocolConformance:
    """Verify JobTemplateProtocol dataclass satisfies the contracts JobTemplateProtocol protocol."""

    def test_job_template_is_instance_of_job_template_protocol(self) -> None:
        """A concrete JobTemplateProtocol must satisfy the @runtime_checkable JobTemplateProtocol protocol."""
        template = JobTemplateProtocol(name="my_task")

        assert isinstance(
            template,
            JobTemplateProtocol,
        ), "JobTemplateProtocol dataclass must be an instance of quadkit.contracts.tasks.JobTemplateProtocol protocol"

    def test_job_template_has_all_required_protocol_fields(self) -> None:
        """Each field declared on the JobTemplateProtocol must exist on a JobTemplateProtocol instance."""
        template = JobTemplateProtocol(name="my_task")

        required_fields = ("name", "args", "kwargs", "priority", "max_retries", "timeout", "depends_on")
        for field_name in required_fields:
            assert hasattr(template, field_name), f"JobTemplateProtocol is missing protocol field: {field_name!r}"

    def test_create_job_produces_conformant_job(self) -> None:
        """JobTemplateProtocol.create_job() must produce a JobProtocol that satisfies the JobProtocol protocol."""
        template = JobTemplateProtocol(name="my_task", priority=5, max_retries=2)
        job = template.create_job()

        assert isinstance(job, JobProtocol)
        assert job.name == "my_task"
        assert job.priority == 5
        assert job.max_retries == 2
