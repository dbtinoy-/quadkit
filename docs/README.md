# Quadkit documentation

Async Python, contract-driven, container-assembled. These pages cover the
five distributions published from this repository — `quadkit-contracts`,
`quadkit`, `quadkit-web`, `quadkit-testing`, and `quadkit-cli` — and only
those. Every Python snippet in them is compiled in CI, and the getting-
started examples run as real tests against the published wheels.

## Getting started

| Page | What you get |
| --- | --- |
| [Installation](getting-started/installation.md) | The five packages, extras, and Python support |
| [Your first app](getting-started/first-app.md) | A working endpoint in about five minutes |
| [Configuration](getting-started/configuration.md) | `application.yaml` and `QK_*` environment overrides |
| [Testing](getting-started/testing.md) | Test your routes without starting a server |

## Concepts

| Page | What it explains |
| --- | --- |
| [Contracts](concepts/contracts.md) | Protocols, types, and the `Result` error model |
| [Dependency injection](concepts/dependency-injection.md) | The container, singletons, and providers |
| [Modules](concepts/modules.md) | Bundling providers and controllers into features |
| [Lifecycle](concepts/lifecycle.md) | `register → boot → start → stop` in order, every time |
| [Async model](concepts/async-model.md) | Async end to end: controllers, server, and tests |

## Guides

Each guide embeds an executable example from `docs/guides/examples/`,
kept byte-identical with the page and executed in CI.

| Page | What it covers |
| --- | --- |
| [Web API](guides/web-api.md) | Path/query/body binding, `status_code`, generated OpenAPI, CSRF posture |
| [Middleware](guides/middleware.md) | The ASGI middleware pattern and registration |
| [Dependency overrides](guides/dependency-overrides.md) | Constructor injection and test doubles before boot |
| [Error handling](guides/error-handling.md) | `Result` mapping, `HTTPError`, problem responses |
| [Production deployment](guides/production-deployment.md) | `web.server` knobs, `quadkit run`, readiness with `/health` |
| [Docker deployment](install.docker.md) | Reference Dockerfile, compose sketch, image verification |
| [Observability](guides/observability.md) | Structured logs, health probes, optional OTel traces, incident runbook |

## Reference and governance

| Page | What it answers |
| --- | --- |
| [Support matrix](reference/support-matrix.md) | Python/OS support, stability tiers, deprecation and support windows |
| [Performance budgets](reference/performance-budgets.md) | Measured boot/latency/memory/CLI baselines, regression-signal policy |
| [Upgrading](reference/upgrading.md) | Minor/major upgrade procedure, deprecation sweep, stay-current checklist |
| [Public roadmap](governance/roadmap.md) | Shipped / next / later, explicit non-goals, and how priorities change |
| [RFC process](governance/rfc-process.md) | Proposing, reviewing, and recording substantial changes |
| [Good first issues](governance/good-first-issues.md) | The newcomer label contract and the maintainer triage rules |
| [Adoption metrics](governance/adoption-metrics.md) | What is measured (CI fixtures, public indexes) and the no-telemetry rule |

## Reference

| Page | What it covers |
| --- | --- |
| [quadkit](reference/quadkit.md) | Core entry points, extras, configuration |
| [quadkit-web](reference/quadkit-web.md) | Controllers, servers, `web.*` configuration, extras |
| [quadkit-testing](reference/quadkit-testing.md) | `AppTestBed`, `WebTestBed`, `TestResponse` |
| [quadkit-cli](reference/quadkit-cli.md) | The `quadkit` command, scaffolding, `quadkit run` |
| [Stability and compatibility](reference/stability.md) | The `0.x` versioning policy, deprecation, Python support |

## Security and contributing

- [Secure configuration](security/secure-configuration.md) — secrets via
  environment, CSRF and security-surface knobs, supply-chain hygiene.
- [Vulnerability reporting](security/vulnerability-reporting.md) —
  embargoed reporting process (authoritative: [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md)).
- [Development setup](contributing/development.md) — DCO, checks, layout
  (authoritative: [CONTRIBUTING.md](https://github.com/dbtinoy-/quadkit/blob/main/CONTRIBUTING.md)).
- [The public repository model](contributing/public-repository-model.md)
  — why this tree contains exactly the five distributions.
- [Release process](contributing/release-process.md) — lockstep
  versioning and what a release validates.

## Examples

- [example-hub](https://github.com/dbtinoy-/quadkit/tree/main/examples/example-hub) — a full application with
  controllers, a DI provider, typed configuration, and tests.
- [storefront](https://github.com/dbtinoy-/quadkit/tree/main/examples/storefront) — a second public example
  application assembled from the same five packages.
- Package-level documentation lives in each distribution:
  [quadkit](https://github.com/dbtinoy-/quadkit/blob/main/core/quadkit/README.md),
  [quadkit-web](https://github.com/dbtinoy-/quadkit/blob/main/packages/quadkit-web/README.md),
  [quadkit-testing](https://github.com/dbtinoy-/quadkit/blob/main/packages/quadkit-testing/README.md),
  [quadkit-cli](https://github.com/dbtinoy-/quadkit/blob/main/packages/quadkit-cli/README.md),
  [quadkit-contracts](https://github.com/dbtinoy-/quadkit/blob/main/core/quadkit-contracts/README.md).
