"""Unit tests for ExecutionHistory workflow execution tracing."""

from __future__ import annotations

from quadkit.workflow.execution.history import ExecutionHistory
from quadkit.workflow.types import GraphResult, NodeResult


class TestExecutionHistory:
    def test_as_dict_returns_structure(self) -> None:
        result = GraphResult(
            final_state={"output": "done"},
            node_results=[
                NodeResult(
                    node_name="a",
                    output={"out": "val"},
                    duration_ms=10.0,
                    error=None,
                    skipped=False,
                ),
            ],
            iterations=1,
            duration_ms=15.0,
            terminated_at="a",
        )
        history = ExecutionHistory(result)
        d = history.as_dict()
        assert d["iterations"] == 1
        assert d["duration_ms"] == 15.0
        assert d["terminated_at"] == "a"
        assert len(d["nodes"]) == 1

    def test_as_text_returns_human_readable(self) -> None:
        result = GraphResult(
            final_state={"output": "done"},
            node_results=[
                NodeResult(
                    node_name="start",
                    output={},
                    duration_ms=5.0,
                    error=None,
                    skipped=False,
                ),
            ],
            iterations=1,
            duration_ms=10.0,
            terminated_at="start",
        )
        history = ExecutionHistory(result)
        text = history.as_text()
        assert "Workflow trace" in text
        assert "start" in text

    def test_error_rendering_omits_exception_text(self) -> None:
        private_error = RuntimeError("token=private at /srv/tenant-42")
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(
                    node_name="failed-step",
                    output={},
                    duration_ms=2.0,
                    error=private_error,
                ),
            ],
            iterations=1,
            duration_ms=2.0,
            terminated_at="failed-step",
        )
        history = ExecutionHistory(result)

        assert history.as_dict()["nodes"][0]["error_type"] == "RuntimeError"
        assert "token=private" not in history.as_text()
        assert "/srv/tenant-42" not in history.as_text()

    def test_failed_nodes_returns_errors(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="ok", output={}, duration_ms=1.0),
                NodeResult(node_name="fail", output={}, duration_ms=2.0, error="oops"),
            ],
            iterations=2,
            duration_ms=5.0,
            terminated_at="fail",
        )
        history = ExecutionHistory(result)
        assert len(history.failed_nodes()) == 1
        assert history.failed_nodes()[0].node_name == "fail"

    def test_succeeded_nodes_returns_successes(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}, duration_ms=1.0),
                NodeResult(node_name="b", output={}, duration_ms=2.0),
                NodeResult(node_name="c", output={}, duration_ms=3.0, error="err"),
            ],
            iterations=3,
            duration_ms=10.0,
            terminated_at="c",
        )
        history = ExecutionHistory(result)
        succeeded = history.succeeded_nodes()
        assert len(succeeded) == 2
        assert {n.node_name for n in succeeded} == {"a", "b"}

    def test_total_node_time_ms_sums_durations(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="a", output={}, duration_ms=10.0),
                NodeResult(node_name="b", output={}, duration_ms=20.0),
                NodeResult(node_name="c", output={}, duration_ms=30.0),
            ],
            iterations=3,
            duration_ms=70.0,
            terminated_at="c",
        )
        history = ExecutionHistory(result)
        assert history.total_node_time_ms() == 60.0

    def test_skipped_nodes_not_counted_as_failed(self) -> None:
        result = GraphResult(
            final_state={},
            node_results=[
                NodeResult(node_name="skip", output={}, skipped=True),
            ],
            iterations=1,
            duration_ms=1.0,
            terminated_at="skip",
        )
        history = ExecutionHistory(result)
        assert len(history.failed_nodes()) == 0
        assert len(history.succeeded_nodes()) == 0
