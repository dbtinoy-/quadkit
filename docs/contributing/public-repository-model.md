# The public repository model

This repository is **generated**: it is produced by an export pipeline
from a development workspace. Its package allow-list is the 18 public-use
distributions in [installation](../getting-started/installation.md), plus their
tests, examples and documentation. Candidate exports may be reviewed before
publication; membership does not mean a version is available on the index.

That design has three user-visible consequences, all of them features:

**What you audit is what you install.** The tree you browse on GitHub
and the tree the wheels build from are the same tree. There are no
private internals permitted downstream of the public packages. Released
cross-package dependencies must resolve from the index like any other dependency;
a local candidate export alone does not establish that availability.

**Internal-only names cannot appear.** During export, the tool chain
checks for and removes references to anything outside the public set —
source, tests, configuration, and documentation. The checks run on every
export, including on pull requests, so this property is enforced rather
than hoped for. Even `quadkit-testing`'s optional extras that pointed at
internal tooling drop out of the public manifest instead of leaking.

**The tests you see are the tests that pass.** Public tests execute from
the exported tree against the built wheels in an isolated environment —
the same "clean-laptop" install you get — and the quickstart examples in
this documentation run the same way (see the CI checks on any pull
request for the rehearsal).

## Contributing within the model

- Open issues and pull requests against this repository as usual —
  review happens here, in the open.
- Changes should use the 18 distributions' public APIs; the checks
  above treat everything else as an error, immediately.
- If a change would need an internal package to make sense, say so in
  the issue instead — that conversation is cheaper than a PR that cannot
  merge.

Continue: [release process](./release-process.md).
