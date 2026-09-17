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
test-harness boot (included in app boot via `WebTestBed`), and CLI startup
plus `quadkit new` project generation (skipped automatically when the CLI
is not on PATH).

The script never fails the build on a regression — it prints a `WARN` line
when a metric exceeds 150% of the recorded baseline. Reviewers treat that
line as a prompt to investigate, not a gate. To bless a new baseline,
replace `baselines.json` with fresh `results.json` (reviewed like any
other change).
