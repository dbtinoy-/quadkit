# Security Policy

## Supported Versions

The Quadkit Framework follows the `0.Y.Z` versioning scheme. Security fixes
are released as patch releases on the latest minor series.

| Version | Supported |
|---------|-----------|
| Latest `0.Y.Z` | ✅ |
| Older minors | ⚠️ Critical fixes only |
| Pre-releases (`rc`, `b`) | ❌ |

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

To report a vulnerability privately, use GitHub's Private Security
Vulnerability Reporting on this repository:

1. Open the repository's **Security** tab.
2. Click **Report a vulnerability**.

Include as much as possible to help us reproduce and assess the issue:

- Affected package(s) and version(s)
- Steps to reproduce (trimmed to the minimal example)
- Impact assessment and any proof of concept

## Handling

- We aim to acknowledge reports within **24 hours**.
- Validated critical issues are prioritized for an immediate patch release.
- Once fixed, a security advisory is published before broader disclosure.

## Security Practices

The framework follows these security practices across the codebase:

- **Secrets** — never stored in YAML; loaded via environment or secret stores.
- **Redaction** — configuration dumps redact secret-like fields
  (`api_key`, `password`, `token`).
- **Ambient capabilities** — clock/identity/hashing override is
  test-only; production paths cannot swap them.
- **Containers** — `testing_mode=True` containers are never used in
  production; frozen containers reject registration and override.
- **Dependencies** — pinned and scanned; baseline guards fail CI on new
  unbounded pins.

See the security guides on the documentation site for secure
configuration guidance and the full vulnerability-reporting process:
https://dbtinoy-.github.io/quadkit/security/