# Project Governance

Quadkit is an Apache-2.0 open-source project maintained by the Quadkit team
and its contributors.

## Roles

### Maintainers

Maintainers review changes, protect the project standards, manage releases,
and guide the technical direction.

### Contributors

Contributors propose improvements, submit pull requests, add tests, improve
documentation, and participate in technical discussions.

## Decision making

Small fixes may be approved through normal pull-request review. Changes to
public APIs, package boundaries, security behavior, or release policy should
include a design discussion or architecture decision record.

Breaking changes require:

- Maintainer approval.
- A migration guide.
- Updated compatibility documentation.
- Tests covering old and new behavior where practical.

## Technical standards

- Python 3.11 or newer.
- Async APIs for I/O-bound operations.
- Type annotations for public APIs.
- Protocol-based extension boundaries.
- Explicit dependency injection.
- Tests for behavior and public contracts.
- Ruff and type-checking compliance.
- Security review for authentication, serialization, networking, and secrets.

## Releases

Releases use PEP 440-compatible versions and are generated from a reviewed
source revision. Release verification includes tests, security checks,
clean-environment installation, documentation checks, and artifact review.

## Community standards

All participants must follow the Code of Conduct. Vulnerabilities must be
reported privately using the process in `SECURITY.md`.
