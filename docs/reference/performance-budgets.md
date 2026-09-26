# Performance budgets

Measured numbers for the operations users feel most, recorded against the
released wheels on every PR and published here. Budgets are a **regression
signal, not a gate**: `benchmarks/measure.py` compares each run against
`benchmarks/baselines.json` and prints a `WARN` line beyond +50% — the
build stays green; reviewers investigate.

## Current baseline

Measured against the wheels of the version recorded in
`benchmarks/baselines.json` (`measured_version`) in a wheel-only Linux /
Python 3.11 environment — the shape CI's verification job uses, with the
in-process test client, no network, and the CLI console script on `PATH`.
The run itself prints a note whenever the installed distributions do not
match that record, so a stale baseline is visible in the job summary.

| Metric | Meaning | Baseline |
| --- | --- | --- |
| `app_boot_ms` | Application boot: providers register+boot via the test harness | 9.7 ms |
| `first_request_ms` | First `GET /hello` after boot | 11.8 ms |
| `request_p50_ms` / `request_p95_ms` | Steady-state POST latency, 200 requests after warmup | 1.74 / 2.18 ms |
| `requests_total_ms` | 200-requests batch (context for the percentiles) | 358.1 ms |
| `peak_memory_mib` | Peak traced memory growth across boot + 50 requests | 0.2 MiB |
| `import_quadkit_ms` | `import quadkit` in a fresh interpreter (median of 5) | 47.4 ms |
| `import_testing_ms` | `import quadkit.testing` in a fresh interpreter (median of 5) | 48.5 ms |
| `cli_version_ms` | CLI cold startup (`quadkit version`) | 154.1 ms |
| `cli_project_generation_ms` | `quadkit new project` scaffolding | 454.6 ms |

Each number is the median of three or more consecutive runs of
`benchmarks/measure.py`, so the table describes a typical run rather than a
lucky one; `request_p50_ms`/`request_p95_ms` are themselves percentiles
over 200 requests within a run.

In-process measurements exclude network and server-stack overhead; absolute
numbers on your host will differ — what CI guards is the **delta against
the baseline**, not the absolute value.

## How CI uses this

Every PR and every release runs `benchmarks/measure.py --baseline
benchmarks/baselines.json` from the wheel-only verification environment and
appends the table to the job summary. A `WARN` line starts a conversation;
it does not block merge. To bless improved (or intentionally changed)
numbers, regenerate `baselines.json` in the same PR that changes them.

## Running locally

From a checkout of this repository with the thirteen distributions installed:

```bash
python benchmarks/measure.py --json results.json --baseline benchmarks/baselines.json
```

The measurement app is built inline by the script (one controller, GET +
POST, CSRF disabled for the measurement only via a scoped
`QK_WEB__SECURITY__CSRF__ENABLED` override) so it is correct from any
working directory.
