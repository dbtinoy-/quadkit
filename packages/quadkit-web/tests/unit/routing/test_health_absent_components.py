"""An unconfigured component is not a broken one (T2.9).

`/health` used to answer 503 with `database` and `redis` unhealthy for any
application that deliberately has neither — which is the shape a web-only
generated project has, and the shape any service that skips an optional
dependency has. The two facts it conflated are different:

* "this application has no database" — a statement about the deployment;
* "this application's database is down" — a statement about correctness, and
  the only one an alert should act on.

The first is reported as ``UNKNOWN`` with its reason and does not decide the
application's status; the second still does. These tests pin both directions,
because a health surface that stays 200 through a real failure is worse than
one that cries wolf.
"""

from __future__ import annotations

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.web.routing.health_checks import WebHealthChecker


class HealthyDB:
    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        return HealthCheckResult(component="database", status=HealthStatus.HEALTHY, message="ok")


class BrokenDB:
    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        raise RuntimeError("db-fail")


async def test_an_app_with_neither_component_reports_healthy() -> None:
    """The web-only case: nothing is configured, so nothing is wrong."""
    response = await WebHealthChecker().check_health()

    assert response.status == HealthStatus.HEALTHY
    assert response.components["database"].status == HealthStatus.UNKNOWN
    assert response.components["redis"].status == HealthStatus.UNKNOWN


async def test_the_absence_says_what_is_missing() -> None:
    response = await WebHealthChecker().check_health()

    assert "database" in (response.components["database"].message or "").lower()
    assert "cache" in (response.components["redis"].message or "").lower()


async def test_a_configured_and_working_component_still_decides() -> None:
    response = await WebHealthChecker(db_provider=HealthyDB()).check_health()

    assert response.status == HealthStatus.HEALTHY
    assert response.components["database"].status == HealthStatus.HEALTHY
    assert response.components["redis"].status == HealthStatus.UNKNOWN


async def test_a_configured_and_broken_component_still_fails_the_app() -> None:
    """The half that must not soften: a real failure is still a failure."""
    response = await WebHealthChecker(db_provider=BrokenDB()).check_health()

    assert response.status == HealthStatus.UNHEALTHY
    assert response.components["database"].status == HealthStatus.UNHEALTHY
    assert "db-fail" in (response.components["database"].message or "")


async def test_an_absent_component_cannot_mask_a_broken_one() -> None:
    """UNKNOWN is not "assume fine": it must not swallow a neighbour's failure."""
    response = await WebHealthChecker(db_provider=BrokenDB()).check_health()

    assert response.components["redis"].status == HealthStatus.UNKNOWN
    assert response.status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_the_route_answers_200_for_an_app_with_no_dependencies(test_bed) -> None:
    """The whole path, unmocked: container resolution → checker → status code.

    Every other route test patches the checker, so the one thing they cannot
    see is whether a *real* application with no database and no cache gets a
    passing answer. That is precisely the shape a web-only deployment has.
    """
    from starlette.testclient import TestClient

    from quadkit.web.di.provider import WebProvider

    web = await test_bed.resolve(WebProvider)
    client = TestClient(web.starlette, raise_server_exceptions=False)

    response = client.get("/health")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == HealthStatus.HEALTHY.value
    # ...and it still says what it does not have, rather than hiding it.
    assert body["components"]["database"]["status"] in {
        HealthStatus.UNKNOWN.value,
        HealthStatus.HEALTHY.value,
    }
