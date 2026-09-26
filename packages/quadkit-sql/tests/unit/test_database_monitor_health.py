
import pytest

from quadkit.sql.monitoring.database_monitor import DatabaseHealthChecker
from quadkit.sql.monitoring.metrics import InMemoryDbMetricsCollector


@pytest.mark.asyncio
async def test_check_database_health_fallback(monkeypatch):
    # Track create_engine calls
    calls = {"count": 0}

    class FailingResult:
        def fetchone(self):
            return None

    class FailingEngine:
        def connect(self):
            class CM:
                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

                def execute(self_inner, t):
                    raise RuntimeError("first-failure")

            return CM()

        def dispose(self):
            pass

    class SuccessfulResult:
        def fetchone(self):
            return (1,)

    class SuccessfulEngine:
        def connect(self):
            class CM:
                def __enter__(self_inner):
                    class Conn:
                        def execute(self2, t):
                            class Result:
                                def fetchone(self3):
                                    return (1,)

                            return Result()

                    return Conn()

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return CM()

        def dispose(self):
            pass

    def fake_create_engine(conn_str, connect_args=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return FailingEngine()
        else:
            return SuccessfulEngine()

    # patch sqlalchemy.create_engine (imported locally in function)
    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)

    checker = DatabaseHealthChecker(InMemoryDbMetricsCollector())

    res = await checker.check_database_health(
        "postgresql://user:pass@localhost/db", timeout=1.0,
    )

    assert res.status == "healthy"
    assert "Database connection successful" in res.message
