#!/usr/bin/env python3
"""Measure Quadkit performance budgets against the INSTALLED distributions.

Run from a virtualenv containing the five public distributions:

    python benchmarks/measure.py                 # print a report
    python benchmarks/measure.py --json out.json # also write machine-readable results
    python benchmarks/measure.py --baseline benchmarks/baselines.json

With ``--baseline``, each metric is compared to the recorded baseline: a
regression beyond +50% prints a WARN line. The exit code stays zero —
budgets are a regression *signal* for reviewers, not a gate (see
docs/reference/performance-budgets.md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

REQUESTS = 200
BOOTS = 3
WARMUP = 10


def build_app():
    """A minimal realistic app: one controller, two routes."""
    import os

    # Stateless measurement traffic carries no cookies; CSRF would reject
    # the POST loop with 403s and measure the wrong thing. Env override so
    # the script is correct from any working directory.
    os.environ.setdefault("QK_WEB__SECURITY__CSRF__ENABLED", "false")

    from quadkit import Application
    from quadkit.web import Controller, WebModule, body, get, post

    class BenchController(Controller):
        @get("/hello")
        async def hello(self) -> dict:
            return {"message": "hello"}

        @post("/echo", status_code=201)
        async def echo(self, payload: dict = body()) -> dict:
            return {"you_sent": payload}

    app = Application()
    app.add_modules([WebModule.configure(controllers=[BenchController])])
    return app


def measure_boot_and_requests() -> dict:
    from quadkit.testing import WebTestBed

    boot_ms: list[float] = []
    first_ms = steady = None
    samples: list[float] = []

    for i in range(BOOTS):
        app = build_app()
        started = time.perf_counter()
        bed = WebTestBed(app)
        asyncio.run(bed.__aenter__())
        boot_ms.append((time.perf_counter() - started) * 1000)

        t0 = time.perf_counter()
        bed.get("/hello").assert_status(200)
        if i == 0:
            first_ms = (time.perf_counter() - t0) * 1000

        if i == BOOTS - 1:
            for _ in range(WARMUP):
                bed.get("/hello")
            started = time.perf_counter()
            for _ in range(REQUESTS):
                t = time.perf_counter()
                bed.post("/echo", json={"n": 1}).assert_status(201)
                samples.append((time.perf_counter() - t) * 1000)
            steady = (time.perf_counter() - started) * 1000

        asyncio.run(bed.__aexit__(None, None, None))

    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    return {
        "app_boot_ms": round(statistics.median(boot_ms), 1),
        "first_request_ms": round(first_ms, 1),
        "request_p50_ms": round(statistics.median(samples), 2),
        "request_p95_ms": round(p95, 2),
        "requests_total_ms": round(steady, 1),
    }


def measure_memory_mib() -> float:
    tracemalloc.start()
    try:
        app = build_app()
        from quadkit.testing import WebTestBed

        bed = WebTestBed(app)
        asyncio.run(bed.__aenter__())
        for _ in range(50):
            bed.get("/hello").assert_status(200)
        asyncio.run(bed.__aexit__(None, None, None))
        _, peak = tracemalloc.get_traced_memory()
        return round(peak / (1024 * 1024), 1)
    finally:
        tracemalloc.stop()


def measure_imports(runs: int = 5) -> dict:
    """Median wall-clock cost of importing a package in a fresh interpreter.

    Each sample is a subprocess, so the number is what a user's test session
    pays before the first line runs — the metric the lazy facades are tuned
    against.
    """
    metrics: dict[str, float] = {}
    for key, module in (
        ("import_quadkit_ms", "quadkit"),
        ("import_testing_ms", "quadkit.testing"),
    ):
        samples: list[float] = []
        for _ in range(runs):
            started = time.perf_counter()
            subprocess.run(
                [sys.executable, "-c", f"import {module}"],
                check=True,
                capture_output=True,
                timeout=120,
            )
            samples.append((time.perf_counter() - started) * 1000)
        metrics[key] = round(statistics.median(samples), 1)
    return metrics


def _time_cli(args: list[str], cwd: str | None = None) -> float | None:
    exe = shutil.which(args[0])
    if exe is None:
        return None
    started = time.perf_counter()
    proc = subprocess.run(
        [exe, *args[1:]], cwd=cwd, capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        return None
    return (time.perf_counter() - started) * 1000


def measure_cli() -> dict:
    result: dict[str, float | str] = {}
    version_ms = _time_cli(["quadkit", "--quiet", "version"])
    result["cli_version_ms"] = round(version_ms, 1) if version_ms is not None else "skipped"
    with tempfile.TemporaryDirectory() as tmp:
        new_ms = _time_cli(["quadkit", "new", "project", "budgetprobe"], cwd=tmp)
    result["cli_project_generation_ms"] = (
        round(new_ms, 1) if new_ms is not None else "skipped"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--baseline", type=Path, default=None)
    args = parser.parse_args()

    try:
        from importlib.metadata import version as _dist_version

        installed_version = _dist_version("quadkit")
    except Exception:  # noqa: BLE001 - measurement must not fail on metadata
        installed_version = "unknown"

    metrics = {
        "python": sys.version.split()[0],
        "quadkit_version": installed_version,
        **measure_boot_and_requests(),
        "peak_memory_mib": measure_memory_mib(),
        **measure_imports(),
        **measure_cli(),
    }

    warns: list[str] = []
    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text())
        measured = baseline.get("measured_version")
        if measured and measured != installed_version:
            warns.append(
                f"NOTE baseline was measured against quadkit {measured}, "
                f"installed is {installed_version}; regenerate "
                "baselines.json in the release PR that re-measures"
            )
        for key, value in metrics.items():
            base = baseline.get(key)
            if isinstance(base, (int, float)) and isinstance(value, (int, float)):
                if value > base * 1.5:
                    warns.append(f"WARN {key}: {value} vs baseline {base} (>+50%)")

    width = max(len(k) for k in metrics)
    print("performance budgets (informational, lower is better)")
    for key, value in metrics.items():
        print(f"  {key:<{width}}  {value}")
    for warn in warns:
        print(warn)
    if args.json:
        args.json.write_text(json.dumps(metrics, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
