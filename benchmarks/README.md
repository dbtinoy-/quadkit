# Performance budgets

`measure.py` records the numbers the project publishes budgets for (see
`docs/reference/performance-budgets.md`), against the **installed**
distributions — measurements are only meaningful against released wheels,
so CI runs this from the wheel-only verification environment on every PR.

```bash
python benchmarks/measure.py
python benchmarks/measure.py --json results.json --baseline benchmarks/baselines.json
```

Metrics: application boot time, first-request latency, steady-state
request p50/p95 (200 POSTs after warmup), peak memory across boot + load,
test-harness boot (included in app boot via `WebTestBed`), the cost of
`import quadkit` and `import quadkit.testing` in a fresh interpreter (the
price a test session pays before its first line), and CLI startup plus
`quadkit new` project generation (skipped automatically when the CLI is
not on PATH).

The script never fails the build on a regression — it prints a `WARN` line
when a metric exceeds 150% of the recorded baseline. Reviewers treat that
line as a prompt to investigate, not a gate.

To bless a new baseline, re-measure in the wheel-only environment with the
CLI on `PATH` (otherwise the CLI metrics report `skipped`), run the script
three or more times, and write the per-metric **median** into
`baselines.json` together with the `quadkit_version` the run printed as
`measured_version`. The median keeps run-to-run noise out of the record;
the +50% headroom absorbs the rest.
