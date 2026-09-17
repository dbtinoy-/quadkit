# Stability and compatibility

Quadkit is in the `0.x` series — alpha, on purpose. You can still shape
it; APIs may shift before `1.0`. This page is the compatibility contract
for everything published from this repository.

## Versioning policy (`0.x`)

- All five distributions — `quadkit-contracts`, `quadkit`,
  `quadkit-web`, `quadkit-testing`, `quadkit-cli` — are released **in
  lockstep with a single version** (currently `0.0.3`). Cross-package
  compatibility is only guaranteed within one released version; do not
  mix `quadkit-web 0.0.2` with a hypothetical `quadkit 0.0.3`.
- **Minor releases** (`0.x → 0.y`) may change or remove public APIs.
  There are no breaking-change-free guarantees before `1.0`.
- **Pin your versions.** In `pyproject.toml` prefer exact pins
  (`quadkit-web==0.0.3`) or tight ranges (`>=0.0.3,<0.1.0`) until `1.0`,
  and read the release notes on every upgrade.

## Deprecation and breaking changes

- When a public API is slated for removal it is first **marked as
  deprecated** (in code and in the changelog), then removed in a
  subsequent release — removals for the whole framework are visible in
  `core/quadkit/CHANGELOG.md`, which ships with the repository.
- Breaking changes land in minor releases, never surprise-patch
  releases; release notes call them out explicitly.
- If a change breaks you unexpectedly, report it:
  [github.com/dbtinoy-/quadkit/issues](https://github.com/dbtinoy-/quadkit/issues) —
  during `0.x`, regressions in documented behavior are treated as bugs.

## Python support

- Every published distribution requires **Python >= 3.11**, matching the
  `requires-python` metadata in all five manifests.
- Support for newer CPython releases is validated as it lands; the floor
  only moves in a minor release, with a note in the changelog.

## API stability tiers

Not everything public-by-import-path is public-by-contract:

- **Stable surface** — top-level imports (`from quadkit import ...`,
  `from quadkit.web import ...`, `from quadkit.testing import ...`) and
  `quadkit-contracts` protocols documented in these pages.
- **Implementation detail** — deep module paths not referenced by the
  docs. They may move in any minor release; prefer documented entry
  points and ask before depending on a deep import.

---

Related: [SECURITY.md](https://github.com/dbtinoy-/quadkit/blob/main/SECURITY.md) for supported versions and
vulnerability reporting, and the [concepts](../concepts/contracts.md)
pages for the APIs these guarantees cover.
