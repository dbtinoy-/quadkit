# Contributing to Quadkit

Thank you for contributing. Quadkit is an Apache-2.0 project and uses the
Developer Certificate of Origin (DCO), not a CLA.

## Before opening a pull request

1. Search existing issues and discussions.
2. Explain the problem and the proposed solution.
3. Add or update tests.
4. Update the relevant documentation and changelog.
5. Run the checks described below.
6. Sign every commit with `git commit -s`.

## Development setup

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The published distributions are `quadkit`, `quadkit-contracts`,
`quadkit-web`, `quadkit-testing`, `quadkit-cli`, `quadkit-sql`,
`quadkit-auth`, `quadkit-cache`, `quadkit-storage`, `quadkit-events`,
`quadkit-tasks`, `quadkit-http` and `quadkit-monitor`. Changes should use
their published public APIs and should not rely on unpublished
implementation packages.

## Pull requests

Keep pull requests focused and describe:

- The user-visible problem.
- The design and compatibility impact.
- Tests added or changed.
- Documentation changes.
- Security or performance considerations.

Breaking changes require a migration note and maintainer approval.

## Commit and PR message format

Use an emoji-prefixed conventional format: `<emoji> <type>(<scope>): <subject>`
— imperative subject, ≤ 72 characters. Pull-request titles follow the same
format; the title is carried into the generated repository when the patch is
replayed upstream.

| Type       | Emoji | Meaning                            | Example                                          |
|------------|-------|------------------------------------|--------------------------------------------------|
| `feat`     | ✨    | New user-visible feature           | `✨ feat(monitor): capture unhandled exceptions` |
| `fix`      | 🐛    | Bug fix                            | `🐛 fix(auth): refresh token expiry race`        |
| `perf`     | ⚡    | Performance improvement            | `⚡ perf(cache): single-flight stampede guards`  |
| `refactor` | ♻️    | Code restructure, no behavior change | `♻️ refactor(scripts): delegate discovery`     |
| `test`     | ✅    | Tests added or updated             | `✅ test(sql): assert tier boundary violations`  |
| `docs`     | 📝    | Documentation only                 | `📝 docs(monitor): Sentry fallback behavior`     |
| `style`    | 🎨    | Format/whitespace, no logic change | `🎨 style(web): normalize quotes`                |
| `chore`    | 🔧    | Maintenance/tooling                | `🔧 chore(git): allowlist tiered paths`          |
| `ci`       | 👷    | CI workflows and config            | `👷 ci: derive members from shared inventory`    |
| `build`    | 📦    | Build system / packaging           | `📦 build: publish quadkit 0.1.3008`             |
| `deps`     | ⬆️    | Dependency upgrade                 | `⬆️ deps: uv sync to 0.8.14`                     |
| `security` | 🔒    | Security hardening fix             | `🔒 security(auth): pin JWT algorithm`           |
| `revert`   | ⏪    | Reverts a previous commit          | `⏪ revert: undo glob members experiment`        |
| `wip`      | 🚧    | Checkpoint / in-progress (drafts)  | `🚧 wip(auth-lane): checkpoint 2026-08-20`       |

Write subjects by their landing state — the behavior the change *delivers* —
rather than the problem it removes, e.g. `🐛 fix(web): honor throttle window
at boundary requests`. Skip vocabulary such as *broken, hack, workaround,
regression*; the history of this repository reads as delivered capability.

## Generated repository model

This repository is generated from the Quadkit source workspace at release
time. The source workspace is the place where maintainers integrate changes;
the generated repository is rebuilt for each release. A pull request here is
reviewed normally, then its patch is replayed into the source workspace so the
change can be included in the next generated release. Preserve authorship and
the `Signed-off-by` trailer when replaying a contribution.

## Security

Do not open a public issue for a vulnerability. Follow `SECURITY.md` and
report it privately.
