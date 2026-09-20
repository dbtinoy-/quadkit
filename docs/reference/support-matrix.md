# Support matrix

What's covered, for how long, and on which runtimes. This page is the
single reference for "is my setup supported".

## Language versions

| Python | Status |
| --- | --- |
| 3.11 | **Supported** — the floor (`requires-python = ">=3.11"`); the full export verification (build, install, import walk, public test suite, docs examples, template tests, docs site, budgets) runs on it on every PR. |
| 3.12 | **Verified** — the released wheels are installed and exercised (module import walk, starter-template tests, getting-started examples) on every PR. |
| 3.13 | **Verified** — same wheel-level verification as 3.12 on every PR. |

## Operating systems

| OS | Status |
| --- | --- |
| Linux (glibc, x86_64/arm64) | **Supported** — primary CI target; the container reference images are Linux. |
| macOS (arm64/x86_64) | **Verified** — development environments; production recommendation is Linux. |
| Windows | **Best effort** — asyncio differences (proactor loop, signal handling) mean some server-shutdown paths behave differently; report issues with a minimal repro. |

## Distributions and deprecation policy

The public surface is exactly five distributions: `quadkit-contracts`,
`quadkit`, `quadkit-web`, `quadkit-testing`, `quadkit-cli`. All five release
in lockstep with the same version number — mixing versions across them is
not a supported configuration.

| Stability tier | Meaning |
| --- | --- |
| Stable (top-level documented imports) | Breaking changes only on a major version bump, with a deprecation release first. |
| Experimental (marked in docstrings/pages) | May change in minor versions; called out in release notes when it does. |
| Internal (anything not reachable from the documented top level) | No compatibility promise; do not import from deep paths. |

Deprecations are announced in two places before removal: the docstring/page
for the API, and the release notes of the version that introduces the
deprecation. A deprecated API stays functional for at least one full minor
release series.

## Release cadence and support window

- Releases are cut from tagged green CI (see
  [release process](../contributing/release-process.md)).
- The latest minor series receives bug fixes; the previous minor series
  receives security fixes until the next minor ships.
- Security fixes are never held for a feature window (see
  [vulnerability reporting](../security/vulnerability-reporting.md)).

## Reporting problems

- Bugs and regressions: GitHub issues using the **bug report** template.
- Feature requests: GitHub issues using the **feature request** template;
  substantial design changes go through the [RFC process](../governance/rfc-process.md).
- Security issues: **never a public issue** — follow
  [vulnerability reporting](../security/vulnerability-reporting.md).

A supported report includes: the Quadkit version (`pip show quadkit`),
Python version, OS, a minimal repro, and the relevant log excerpt. Issues
triaged as confirmed bugs get a milestone assignment within one week.
