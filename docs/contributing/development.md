# Development setup

This page summarizes [`CONTRIBUTING.md`](https://github.com/dbtinoy-/quadkit/blob/main/CONTRIBUTING.md) — read
the file for the authoritative checklist.

**DCO, not CLA.** Quadkit is an Apache-2.0 project that uses the
Developer Certificate of Origin: sign every commit with
`git commit -s`.

## Before opening a pull request

1. Search existing issues and discussions.
2. Explain the problem and the proposed solution.
3. Add or update tests.
4. Update the relevant documentation and changelog.
5. Run the checks below.
6. Sign every commit (`git commit -s`).

## Setup and checks

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

[uv](https://docs.astral.sh/uv/) manages the environment; the lockfile
pins the toolchain. Tests run with pytest (async support comes from the
workspace configuration — no manual event-loop plumbing).

## The public distributions

The supported public distributions are `quadkit`, `quadkit-contracts`,
`quadkit-web`, `quadkit-testing`, and `quadkit-cli` — and that's the
whole public surface. Contributions should use their published public
APIs and must not introduce dependencies on name prefixes outside that
set: the export tooling re-checks this on every build, and the
dependency check (`scripts/check_public_dependencies.py`) runs the same
invariant locally.

Layout reminder: contracts and the core framework live under `core/`;
the feature packages and CLI live under `packages/`. Public examples
under `examples/` are the reference for how the pieces compose.

Continue with [the public repository model](./public-repository-model.md)
to understand how this repository is produced.
