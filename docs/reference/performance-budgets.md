# Performance budgets

Measured numbers for the operations users feel most, recorded against the
released wheels on every PR and published here. Budgets are a **regression
signal, not a gate**: `benchmarks/measure.py` compares each run against
`benchmarks/baselines.json` and prints a `WARN` line beyond +50% — the
build stays green; reviewers investigate.

## Current baseline

Measured in the CI-equivalent rehearsal environment (Linux, Python 3.11,
in-process test client — no network) against the wheels of the version
recorded in `benchmarks/baselines.json` (`measured_version`); the run
itself prints a note whenever the installed distributions do not match
that record.

| Metric | Meaning | Baseline |
| --- | --- | --- |
| `app_boot_ms` | Application boot: providers register+boot via the test harness | 8.6 ms |
| `first_request_ms` | First `GET /hello` after boot | 12.7 ms |
| `request_p50_ms` / `request_p95_ms` | Steady-state POST latency, 200 requests after warmup | 1.65 / 1.9 ms |
| `requests_total_ms` | 200-requests batch (context for the percentiles) | 339.5 ms |
| `peak_memory_mib` | Peak traced memory growth across boot + 50 requests | 0.2 MiB |
| `cli_version_ms` | CLI cold startup (`quadkit version`) | 562.6 ms |
| `cli_project_generation_ms` | `quadkit new project` scaffolding | 562.3 ms |

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

From a checkout of this repository with the five distributions installed:

```bash
python benchmarks/measure.py --json results.json --baseline benchmarks/baselines.json
```

The measurement app is built inline by the script (one controller, GET +
POST, CSRF disabled for the measurement only via a scoped
`QK_WEB__SECURITY__CSRF__ENABLED` override) so it is correct from any
working directory.
