# Contributing to Quadkit Framework

Thank you for your interest in contributing to the Quadkit Framework!

> **Note**: Quadkit is **alpha (0.1.x)** and licensed under the [Apache License 2.0](./LICENSE).
> External contributions are welcome.
> All contributions are accepted under the Apache License 2.0 — sign off your commits
> (`git commit -s`) to certify the [DCO](https://developercertificate.org/).
> This is maintained by a small team: reviews are best-effort, with no support SLA.

## Licensing and sign-off

There is **no CLA to sign**. Quadkit uses the
[Developer Certificate of Origin](https://developercertificate.org/): you keep
the copyright in your work, and you certify that you have the right to submit
it by signing off each commit.

```bash
git commit -s          # adds: Signed-off-by: Your Name <you@example.com>
```

The name and email in the trailer must match the commit author. CI checks
every commit in a pull request and tells you how to fix it if one is missing
(`git rebase --signoff <base>`).

Under [section 5 of Apache-2.0](./LICENSE), anything you submit for inclusion
is offered under that same licence — so the DCO plus the licence is all that
is needed.

## How your pull request gets merged

This repository is **generated** from a larger private monorepo, so pull
requests here cannot be merged with the button.

Instead, an approved change is replayed into the monorepo with `git am`,
which keeps **you as the commit author** and preserves your `Signed-off-by`
trailer. Your pull request is then **closed with a link to the release that
contains your change**.

A closed pull request here is not a rejection. If your change was approved,
it shipped — check the linked release, where you will appear in the history
as its author.

## Getting Started

### Prerequisites
- Python 3.11+
- `uv` package manager
- Docker (for integration testing)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/dbtinoy-/quadkit.git
cd quadkit

# Install dependencies
make dev

# Run tests (offline unit surface; integration-marked tests are deselected by default)
make test

# Run the live-service integration suite
make integration-test

# Check code quality
make check
```

## Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feat/feature-name
```

### 2. Make Changes
- Ensure all tests pass: `make test`
- Check linting: `make lint`
- Verify type safety: `make type`

### 3. Commit with Meaningful Messages
```bash
git commit -m "feat: add new feature description"
```

**Commit message format**:
- `feat: ` — New feature
- `fix: ` — Bug fix
- `docs: ` — Documentation
- `test: ` — Test additions/updates
- `refactor: ` — Code refactoring
- `perf: ` — Performance improvements
- `chore: ` — Maintenance

### 4. Run Full CI Locally
```bash
make ci
```

### 5. Push and Create Pull Request
```bash
# MANDATORY: Rebase before pushing — never use git merge
git pull --rebase origin main
git push origin feat/feature-name
```

> **MANDATORY**: Never use `git merge`. Always `git pull --rebase origin main`
> before pushing. Merge commits pollute history, block clean reverts, and
> create noisy auto-generated messages like
> `Merge branch 'xxx' of github.com:... into HEAD`.
> If you see a merge commit in your PR, rebase it out before requesting review.

Create a Pull Request with:
- Clear title describing the change
- Description of what and why
- Reference to related issues
- Evidence that tests pass

## Code Standards

The repository keeps the engineering rules in one authoritative place — do not
duplicate them here.

- [AGENTS.md](./AGENTS.md) — **framework implementation standards** (architecture, contracts, DI, providers/modules, code style, testing, codegen).
- [DEVELOPMENT.md](./DEVELOPMENT.md) — **repository engineering** (build/lint/type/test commands, CI, versioning, git rules).
- [CONTRIBUTING.md](./CONTRIBUTING.md) — human-facing workflow (this file).

Key minimums you are expected to meet: Python 3.11+, complete type annotations,
`Result[T, E]` for expected domain failures, async I/O, Google-style docstrings,
and strict package-boundary compliance.

## Testing

### Run Unit Tests
```bash
make test
```

### Run Integration Tests
```bash
# Start services
make integration-deps

# Run tests
make integration-test

# Stop services
make integration-stop
```

### Run Specific Tests
```bash
make test-pkg PKG=quadkit-web
uv run pytest packages/quadkit-web/tests/unit/ -v
```

For the complete command reference (lint, format, type, coverage, CI, versioning) see [DEVELOPMENT.md](./DEVELOPMENT.md).

## Linting & Formatting

### Check Code Quality
```bash
make check    # lint + format + type check (no writes)
make lint     # Just lint check
make type     # Just type check
```

### Auto-Fix Issues
```bash
make lint-fix  # Auto-fix lint issues
make fmt       # Auto-format code
```

### Verify Import Boundaries
```bash
make lint-boundaries
```

## Documentation

### Building Local Documentation
```bash
make docs
```

This regenerates the API surface files from source.

### Writing Documentation
- Keep README.md up-to-date with major changes
- Document architectural decisions in `docs/adr/` (Architecture Decision Records)
- Update CHANGELOG.md for all changes

## Release Process

### Version Management
- Versions follow `0.<minor>.<patch><build>`.
- Versions are **per-package**; a package bumps only when that package changes.
- See [DEVELOPMENT.md](./DEVELOPMENT.md#36-versioning) for the exact scheme and the `make version-bump` flow.

### Creating a Release
Use the repository's version tooling — do **not** hand-edit versions or bump
every package for a single change.

```bash
make version-bump PKG=<pkg> APPLY=--apply
# then publish that package
cd <pkg> && uv build && uv publish
```

## Code Review Process

### What to Expect
- All PRs require approval from at least 1 maintainer
- CI checks must pass (tests, linting, type safety, coverage)
- Import boundary contracts must be respected
- No breaking changes without discussion

### Review Checklist
- ✅ Code follows style guidelines
- ✅ All tests pass
- ✅ Type annotations complete
- ✅ Documentation updated
- ✅ CHANGELOG.md updated
- ✅ No new dependencies added (discuss first)
- ✅ No import boundary violations

## Common Tasks

### Add a New Package
```bash
# Create the package structure under the right tier:
#   core/            quadkit, quadkit-contracts
#   packages/        backend packages (web, sql, cache, ...)
#   packages/    ai/, apps/, multimedia/ families
mkdir -p packages/quadkit-newfeature/src/quadkit/newfeature
cd packages/quadkit-newfeature
# copy pyproject.toml / README.md skeletons from a sibling package
# (e.g. packages/quadkit-web), then edit them for the new package
```

### Add a Dependency
1. Add to `pyproject.toml`
2. Run `uv sync`
3. Commit lock file changes

### Add a Workspace Package
After adding the package (and its `src/` entry to `[tool.mypy] mypy_path`),
regenerate editor import paths so Pylance resolves it:

```bash
uv run python dev/generators/vscode_settings.py
```

### Update Import Boundaries
Edit `.importlinter` to define new contracts before implementing the feature.

## Questions or Issues?

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with a minimal reproduction
- **Security issues**: Report to security@quadkit.dev (do not open public issues — see [SECURITY.md](./SECURITY.md))

---

**Thank you for contributing to Quadkit Framework!** 🚀
