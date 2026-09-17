# Release process

Releases are continuous and mechanical from a contributor's point of
view; this page describes the observable contract.

## Versioning

All five distributions release **in lockstep** under a single version
(currently `0.0.3`, in the `0.x` series). Cross-package compatibility
is defined within one released version — never mix versions across the
five. The full policy, including deprecation and Python-support rules,
lives in [stability](../reference/stability.md).

## Where versions and changes are recorded

- Each distribution's version is the `version` field of its own
  `pyproject.toml` (`core/quadkit/pyproject.toml`,
  `core/quadkit-contracts/pyproject.toml`, `packages/*/pyproject.toml`);
  the five must always read identically.
- User-visible changes are recorded in `core/quadkit/CHANGELOG.md`,
  which ships with the repository — read it on every upgrade during the
  `0.x` series.

## What a release validates before it ships

A release is only published after the release pipeline has:

1. Re-generated this public tree and passed all export checks
   (public-surface scans, dependency boundary, governance files).
2. Built the five wheels from the exported tree.
3. Installed them into an isolated environment and run the public test
   suite from the exported checkout — the "fresh laptop" rehearsal.
4. Run this documentation set's accuracy checks and executed the
   quickstart examples from the exported tree.

In short: if a tag `v0.0.2` exists on this repository, everything above
was green against exactly what you can browse — and the same rehearsal
runs on every pull request, so CI failures you see are the real gate.

## Contributing to a release

Contributors don't cut releases; maintainers do
(see [`GOVERNANCE.md`](https://github.com/dbtinoy-/quadkit/blob/main/GOVERNANCE.md)). Your part is
changelog-and-release-note hygiene: user-visible changes land with a
changelog entry in the same PR (see
[development setup](./development.md)).
