"""Unit tests for DBMetricsExporter"""

import pytest

from quadkit.monitor.backends.db_exporter import DBMetricsExporter


class DummyDB:
    def __init__(self):
        self.calls = []

    async def execute_query(self, sql, params=None, **kwargs):
        self.calls.append((sql, params))


@pytest.mark.asyncio
async def test_db_exporter_inserts():
    db = DummyDB()
    exp = DBMetricsExporter(db, table="metrics_samples")

    await exp.counter("a", 1, {"env": "test"})
    await exp.gauge("g", 3.14, {})
    await exp.histogram("h", 0.5, {})

    assert len(db.calls) == 3
    assert any("INSERT INTO metrics_samples" in c[0] for c in db.calls)
