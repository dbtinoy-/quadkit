# Changelog

All notable changes to the public quadkit distributions are summarized here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Documentation links and package metadata now point at
  `https://oridecon.dev/quadkit/`. The retired GitHub Pages site and the
  old placeholder domain are gone from the published tree, and error-code
  links resolve through the canonical registry.

## [0.0.4] — 2026-09-19

### Added

- **Self-hosted documentation UI.** The Swagger UI and ReDoc assets are
  vendored inside `quadkit-web` and served by the application itself under
  `/docs-static`: the default `/docs` and `/redoc` pages make zero
  third-party requests. (Swagger UI 5.10.3, Apache-2.0; ReDoc 2.5.4, MIT —
  see `packages/quadkit-web/src/quadkit/web/static/docs/VENDOR-NOTICES.txt`.)
- **CDN opt-in for docs assets.** The new `web.api_docs.cdn_base` setting
  (default `null` = serve locally) loads the same asset filenames from a
  CDN or private mirror; its origin is automatically allowed in the CSP.
  The per-asset `web.swagger_js_url` / `web.swagger_css_url` /
  `web.redoc_js_url` overrides still take precedence, and the boot log
  states the active mode (`local` / `cdn` / `custom`).

### Changed

- **Faster request path.** The default web middleware stack executes one
  DI scope per request (previously two), and the parameter binder is
  precomputed at route-wrap time for request/context-only handlers. Raw
  ASGI hello-route cost dropped about 31%.
- **Faster CLI cold start.** Commands resolve lazily and the CLI package
  imports on demand: `quadkit version` on an installed wheel dropped from
  ~563 ms to ~178 ms in the CI baseline (about −68%).
- **Per-application registries.** Route and controller registries are
  instances owned by each `WebProvider`, so two applications in one
  process never see each other's routes. The module-level
  `route_registry` / `controller_registry` globals were removed;
  `@controller` registers into the application being configured and is a
  safe no-op (with a warning) outside a registration context. Declare
  controllers with `WebProvider(controllers=...)` or
  `@module(controllers=...)` as before.

- **No shared instances in `quadkit-testing`.** `quadkit.testing.lib` shipped
  `test_assertions` and `test_data_factory` as module-level instances, so a
  test that mutated one changed what the next test saw. Both are gone —
  `TestAssertions` and `TestDataFactory` are the helpers, the `assertions` and
  `test_data` fixtures hand each test a fresh one, and
  `InMemoryDistributedLock` no longer falls back to a process-wide lock store:
  a lock with no `store` gets its own, and `force_release` /
  `get_all_locks` now require the store the caller means, so lock state
  cannot leak between tests. Pass one `InMemoryLockStore` to the locks that
  must coordinate (the `TestEnvironment` does this for you).
- **One request-ID implementation.** `RequestIDMiddleware` duplicated
  `RequestContextMiddleware` — same id format, same inbound-header handling —
  and both documented the other as the source of the id, so an app that
  mounted the exported `RequestIDMiddleware` answered with two
  `X-Request-ID` headers (last wins) and a request context whose id could
  differ from the response header. The duplicate is gone:
  `RequestContextMiddleware` is the single implementation, now exported from
  `quadkit.web.middleware`, and `quadkit.web.middleware.request_id` keeps the
  readers (`get_request_id_from_request`, `RequestIDLogFilter`).

### Security

- **One error contract for every failure.** Every failure a Quadkit app
  answers — a raised domain error, request validation, an unhandled
  exception, an unknown route or method, and a CSRF rejection — now renders
  `application/problem+json` (RFC 7807). Previously an unhandled exception
  and a CSRF rejection answered the legacy
  `{"success": false, "error": {...}}` envelope over `application/json`, and
  an unknown route or method answered Starlette's default `text/plain`, so a
  client that keyed on the media type missed those failures entirely. A
  `500` reports `"type": "urn:quadkit:internal-error"` with a generic detail;
  a debug-mode app (`QK_DEBUG`) adds `exception_type` and `traceback`
  problem extensions.
- **API documentation is withheld in production.** `web.api_docs.enabled`
  is now tri-state: unset (the default) serves `/docs`, `/redoc` and
  `/openapi.json` outside production and withholds them in production, so a
  deployment no longer advertises its schema unless the operator opts in
  with `web.api_docs.enabled: true`. `false` withholds them everywhere —
  the endpoints, their vendored `/docs-static` assets and the route-scoped
  CSP all follow that one answer (previously the endpoints were served even
  with the setting off). Production builds that serve the docs log
  `api_docs_served_in_production` at boot; the security guide states the
  posture.
- **Inbound request ids are sanitized.** Client-supplied `X-Request-ID`
  values are honored only when they match `[A-Za-z0-9_-]{1,64}`; anything
  else (CRLF, control characters, oversized, non-ascii, or malformed
  header bytes — previously a server error) is dropped and a fresh id is
  generated. The rejected value is never echoed.
- **Stricter Content-Security-Policy by default.** The default directives
  no longer allow `unsafe-inline` / `unsafe-eval` or any third-party CDN
  host, and `connect-src` tightens from `https: wss: ws:` to `'self'`.
  Documentation routes carry a strict route-scoped CSP; other routes keep
  the application's configured policy.
- **Redaction matcher gaps closed.** `cookie`, `set_cookie`,
  `session_cookie`, `bearer`, `bearer_token`, `x-api-key`, and `x_api_key`
  fields are masked in structured logs; benign lookalikes such as
  `cookie_count` or `token_count` are unaffected.

## [0.0.3] — 2026-09-17

Initial public staging release of the five distributions: the
`quadkit` core (DI container, modules, config, logging, domain
primitives), `quadkit-contracts` protocol layer, `quadkit-web` ASGI
layer, `quadkit-cli` scaffolding and generators, and `quadkit-testing`
test harness. Introduced the public repository layout, the docs site,
the starter examples, and the runnable feature tour.

[Unreleased]: https://github.com/dbtinoy-/quadkit/compare/v0.0.4...HEAD
[0.0.4]: https://github.com/dbtinoy-/quadkit/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/dbtinoy-/quadkit/releases/tag/v0.0.3
