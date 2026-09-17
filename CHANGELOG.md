# Changelog

All notable changes to the five public quadkit distributions — `quadkit`,
`quadkit-contracts`, `quadkit-web`, `quadkit-cli`, and `quadkit-testing` —
are summarized here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Security

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

[Unreleased]: https://github.com/dbtinoy-/quadkit/compare/v0.0.3...HEAD
[0.0.3]: https://github.com/dbtinoy-/quadkit/releases/tag/v0.0.3
