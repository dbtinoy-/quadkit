"""Exercise the real task-console composition root through HTTP.

The app seeds four jobs on boot (``send_welcome_email``, ``resize_image``,
``flaky_report``, ``always_fails``) through the real ``quadkit-tasks``
worker pool. Since no ``RetryPolicyProtocol`` is wired, ``flaky_report``'s
first attempt fails and lands in the DLQ (see ``services/handlers.py``) —
retrying it from the DLQ re-enqueues the same job and its in-process
attempt counter eventually lets it succeed.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest


async def _wait_until(predicate, *, timeout: float = 3.0, interval: float = 0.05) -> bool:
    """Poll ``predicate`` (a zero-arg async callable) until it returns truthy."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await predicate():
            return True
        await asyncio.sleep(interval)
    return await predicate()


@pytest.mark.asyncio
async def test_health_endpoint_reports_real_provider_status(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/tasks/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"healthy", "degraded", "unhealthy"}
    assert "submitted_count" in body["details"]
    assert "dlq_count" in body["details"]


@pytest.mark.asyncio
async def test_boot_seeds_four_demo_jobs(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/tasks/submitted")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    names = {job["name"] for job in body["jobs"]}
    assert names == {
        "send_welcome_email",
        "resize_image",
        "flaky_report",
        "always_fails",
    }


@pytest.mark.asyncio
async def test_seeded_jobs_complete_with_unwrapped_handler_payloads(
    client: httpx.AsyncClient,
) -> None:
    """Completed results must carry the handler's raw return value in `data`,
    not a nested JobResult (regression test for the double-wrap bug fixed in
    ``quadkit-tasks``' ``TaskWorker._execute_job``)."""

    async def _has_results() -> bool:
        body = (await client.get("/api/tasks/results")).json()
        return len(body["completed"]) >= 2

    assert await _wait_until(_has_results)

    body = (await client.get("/api/tasks/results")).json()
    by_name = {r["name"]: r for r in body["completed"]}

    assert "send_welcome_email" in by_name
    email_result = by_name["send_welcome_email"]
    assert email_result["success"] is True
    assert email_result["data"] == {
        "user_id": "u-1",
        "email": "u1@example.com",
        "delivered": True,
    }
    # The bug this regression-tests: `data` must not itself look like a
    # JobResult (no nested success/data/error/duration keys).
    assert "success" not in email_result["data"]
    assert "duration" not in email_result["data"]

    assert "resize_image" in by_name
    resize_result = by_name["resize_image"]
    assert resize_result["data"] == {
        "image_id": "img-42",
        "width": 1024,
        "height": 768,
        "resized": True,
    }


@pytest.mark.asyncio
async def test_always_fails_lands_in_the_dead_letter_queue(
    client: httpx.AsyncClient,
) -> None:
    async def _has_dlq_entry() -> bool:
        body = (await client.get("/api/tasks/dlq")).json()
        return any(e["job_name"] == "always_fails" for e in body["entries"])

    assert await _wait_until(_has_dlq_entry)

    body = (await client.get("/api/tasks/dlq")).json()
    entry = next(e for e in body["entries"] if e["job_name"] == "always_fails")
    assert entry["kwargs"] == {"reason": "seeded DLQ example"}
    assert "permanent failure" in entry["error"]


@pytest.mark.asyncio
async def test_flaky_report_retries_from_dlq_until_it_succeeds(
    client: httpx.AsyncClient,
) -> None:
    """The seeded flaky_report fails once and is DLQ'd; retrying it from the
    DLQ re-enqueues the same job, and its second attempt still fails (2 of 3),
    landing back in the DLQ. A third retry finally succeeds."""

    async def _flaky_in_dlq() -> bool:
        body = (await client.get("/api/tasks/dlq")).json()
        return any(e["job_name"] == "flaky_report" for e in body["entries"])

    assert await _wait_until(_flaky_in_dlq)
    dlq = (await client.get("/api/tasks/dlq")).json()
    job_id = next(
        e["job_id"] for e in dlq["entries"] if e["job_name"] == "flaky_report"
    )

    # Attempt 2: still fails (< 3), lands back in the DLQ under a new job id.
    retried = await client.post(f"/api/tasks/dlq/{job_id}/retry")
    assert retried.status_code == 200
    new_job_id = retried.json()["id"]

    async def _second_attempt_dlqd() -> bool:
        body = (await client.get("/api/tasks/dlq")).json()
        return any(
            e["job_name"] == "flaky_report" and e["job_id"] != job_id
            for e in body["entries"]
        )

    assert await _wait_until(_second_attempt_dlqd)
    dlq2 = (await client.get("/api/tasks/dlq")).json()
    second_job_id = next(
        e["job_id"]
        for e in dlq2["entries"]
        if e["job_name"] == "flaky_report" and e["job_id"] != job_id
    )

    # Attempt 3: succeeds.
    retried_again = await client.post(f"/api/tasks/dlq/{second_job_id}/retry")
    assert retried_again.status_code == 200
    third_job_id = retried_again.json()["id"]

    async def _third_attempt_completed() -> bool:
        result = await client.get(f"/api/tasks/jobs/{third_job_id}")
        return result.status_code == 200

    assert await _wait_until(_third_attempt_completed)
    final = (await client.get(f"/api/tasks/jobs/{third_job_id}")).json()
    assert final["success"] is True
    assert final["data"]["generated"] is True
    assert new_job_id != job_id != third_job_id


@pytest.mark.asyncio
async def test_retry_unknown_dlq_job_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/tasks/dlq/does-not-exist/retry")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_result_for_unknown_job_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/tasks/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_enqueue_rejects_unknown_task_name(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/tasks", json={"task": "delete_the_prod_database", "kwargs": {}}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_enqueue_rejects_non_object_kwargs(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/tasks", json={"task": "compute_digest", "kwargs": "not-an-object"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_enqueue_and_wait_for_a_real_job(client: httpx.AsyncClient) -> None:
    enqueued = await client.post(
        "/api/tasks",
        json={"task": "compute_digest", "kwargs": {"payload": "hello"}},
    )
    assert enqueued.status_code == 200
    job_id = enqueued.json()["id"]

    waited = await client.get(f"/api/tasks/jobs/{job_id}/wait")
    assert waited.status_code == 200
    result = waited.json()
    assert result["success"] is True
    assert result["data"] == {"payload_len": 5, "checksum": sum(map(ord, "hello")) % 997}


@pytest.mark.asyncio
async def test_worker_stats_reports_the_real_pool(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/tasks/workers")
    assert response.status_code == 200
    body = response.json()
    assert body  # Real WorkerPool.get_worker_stats() payload, non-empty.


@pytest.mark.asyncio
async def test_scheduled_jobs_include_the_heartbeat(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/tasks/scheduled")
    assert response.status_code == 200
    body = response.json()
    text = str(body)
    assert "scheduled_heartbeat" in text


@pytest.mark.asyncio
async def test_purge_dlq_removes_every_entry(client: httpx.AsyncClient) -> None:
    async def _has_any_dlq_entry() -> bool:
        body = (await client.get("/api/tasks/dlq")).json()
        return body["count"] > 0

    assert await _wait_until(_has_any_dlq_entry)

    purged = await client.post("/api/tasks/dlq/purge")
    assert purged.status_code == 200
    assert purged.json()["ok"] is True
    assert purged.json()["purged"] >= 1

    after = await client.get("/api/tasks/dlq")
    assert after.json()["count"] == 0
