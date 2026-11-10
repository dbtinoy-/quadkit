"""Tests for the metric generator's authored definition fields."""

from __future__ import annotations

from quadkit.monitor.cli.generators.metric import MetricGenerator


def test_metric_unit_and_description_options_are_emitted(tmp_path) -> None:
    generator = MetricGenerator(output_dir=tmp_path / "metrics")
    generator.generate(
        "orders_placed",
        unit="sentinel_units",
        description="SENTINEL_METRIC_DESCRIPTION",
    )

    content = (tmp_path / "metrics" / "orders_placed_metric.py").read_text()
    assert "description = 'SENTINEL_METRIC_DESCRIPTION'" in content
    assert "unit = 'sentinel_units'" in content
    compile(content, "orders_placed_metric.py", "exec")


def test_metric_defaults_are_preserved_without_options(tmp_path) -> None:
    generator = MetricGenerator(output_dir=tmp_path / "metrics")
    generator.generate("orders_placed")

    content = (tmp_path / "metrics" / "orders_placed_metric.py").read_text()
    assert "description = 'The OrdersPlaced metric'" in content
    assert "unit = 'ms'" in content
