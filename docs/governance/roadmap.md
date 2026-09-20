# Public roadmap

Directional, honest, and revised in the open. Dates are quarter-granularity
intentions, not commitments; scope beats schedule. Entries link to tracking
issues once work starts.

## Shipped

- **Five-distribution public release** — `quadkit-contracts`, `quadkit`,
  `quadkit-web`, `quadkit-testing`, `quadkit-cli` in lockstep versions,
  generated from a private monorepo with a verified export pipeline.
- **Docs as code** — every page validated in CI; getting-started and guide
  examples execute as real tests against the published wheels.
- **Official starter templates** — seven minimal services under
  `examples/` (minimal API, authenticated API, database-backed API,
  background worker, WebSocket service, multi-tenant service, AI
  integration seam), each tested from the exported tree in CI.
- **Contract boundary enforcement** — the `quadkit.contracts` namespace is
  import-pure, dependency-floored, and gate-checked on every PR.
- **Performance budgets in CI** — `benchmarks/measure.py` runs on every PR
  and release against the recorded baselines, as a regression signal
  rather than a gate (see
  [performance budgets](../reference/performance-budgets.md)).

## Next

- **Documentation hosting** — a built docs site (search, versioned pages)
  published from this tree on every release.
- **Typed-first developer experience** — deeper `py.typed` coverage across
  the web layer so IDEs resolve route signatures end to end.

## Later

- **More official templates** — driven by observed adoption questions;
  candidates surface through the RFC process.
- **Ecosystem integrations guide set** — opinionated adapters for common
  brokers and databases, published as recipes rather than bundled deps.
- **CLI scaffolding depth** — richer `quadkit new` output (CI workflow,
  Dockerfile) informed by the starter templates.
- **CLI environment and upgrade commands** — `quadkit doctor`
  (installation/config sanity checks) and `quadkit upgrade` (guided
  version bumps); until they land, the manual procedure in
  [Upgrading](../reference/upgrading.md) is the supported path.

## Explicit non-goals

- **No private-package sprawl**: anything shipped publicly must be
  maintainable by the public CI gates alone; capability that can't meet
  that bar does not ship.
- **No ORM in the core**: data access stays repository-pattern + driver of
  your choice, demonstrated by the database template.
- **No synchronous compatibility shim**: the async model is the model.

## How priorities change

This page is modified only through the normal review process: a PR
proposing edits, reviewed like code, linked to the evidence that motivated
the change (user reports, RFC outcomes, maintainer capacity). If you think
the order is wrong, open an RFC per the
[RFC process](rfc-process.md) — roadmap changes are its most common output.
