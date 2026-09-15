# Project Governance

## Overview

The Quadkit Framework is an **open-source** project maintained by Quadkit, licensed under the [Apache License 2.0](./LICENSE). This document describes the project structure, decision-making process, and roles.

## Project Leadership

### Project Leads
- **Architecture**: Responsible for framework design and architectural decisions
- **Quality**: Oversees testing, linting, and quality standards
- **Releases**: Manages versioning and PyPI publication

### Core Maintainers
- Review and approve pull requests
- Maintain code quality and standards
- Handle security reports
- Guide technical direction

### Contributors
- Community members and partners
- Submit changes via pull requests
- Follow contributing guidelines

## Decision-Making Process

### Design Decisions
1. **Discussion**: Propose in architecture review meeting
2. **Documentation**: Capture in ADR (Architecture Decision Record)
3. **Implementation**: Code review and approval
4. **Feedback**: Gather feedback during code review

### Architecture Changes
- Require approval from 2+ project leads
- Should be documented in `docs/adr/`
- Must consider impact on all workspace packages

### Breaking Changes
- Require explicit approval from project leadership
- Must include migration guide
- Should be communicated well in advance

### Feature Additions
- Proposed via issue or discussion
- Code reviewed by maintainers
- Must include tests and documentation
- Must not violate package boundaries

## Code Standards

### Language
- Python 3.11+
- Async/await for all I/O
- Complete type annotations
- Result[T, E] for domain errors

### Testing
- 80%+ coverage requirement
- @pytest.mark.asyncio for async tests
- Unit + integration tests

### Quality
- Ruff linting enforced in CI
- Mypy type checking via `make type` (core, web, and all qualified packages)
- Import boundary compliance (`.importlinter`)

### Documentation
- Google-style docstrings
- README.md for each package
- CHANGELOG.md updates
- API documentation current

## Architectural Principles

### The Five Pillars
1. **Contracts** — Protocol-based service boundaries
2. **Providers** — Lifecycle-aware dependency providers
3. **Container** — Dependency injection container
4. **Constructor Injection** — Explicit dependency declaration
5. **IoC** — Inversion of Control via the container

### Package Boundaries
- **quadkit-contracts**: Zero dependencies (pure interfaces)
- **quadkit**: Core framework only
- **quadkit-***: Extensions, independent of each other
- **quadkit.ai**: Orchestrator for AI sub-packages

See `.importlinter` for enforced contracts.

## Release Process

### Version Numbering
- Format: `MAJOR.MINOR.PATCH[pre-release]`
- Example: `0.1.1`, `0.1.1b1`, `0.1.1rc1`
- Follows Semantic Versioning

### Release Steps
1. Update version in all `pyproject.toml` files
2. Update CHANGELOG.md
3. Run full test suite: `make ci`
4. Create git tag: `git tag v0.1.1`
5. Push changes and tag
6. Build and publish to PyPI: `uv build && uv publish`

### Release Cadence
- No fixed schedule (release when ready)
- Critical fixes released immediately
- Regular maintenance releases as needed
- Pre-releases (alpha, beta) for testing

## Contributing Requirements

### Eligibility
- Open to all contributors
- Must follow the [Code of Conduct](./CODE_OF_CONDUCT.md)
- Must follow contributing guidelines

### Process
1. Create feature branch: `git checkout -b feat/feature-name`
2. Make changes following code standards
3. Run tests: `make ci`
4. Create pull request with description
5. Address review feedback
6. Merge after approval

### Approval Requirements
- ✅ CI passes (tests, linting, type checks)
- ✅ At least 1 maintainer approval
- ✅ Code review complete
- ✅ Import boundaries respected

## Conflict Resolution

### Minor Disagreements
- Discuss in pull request comments
- Seek consensus
- Falls back to maintainer decision

### Major Disagreements
- Escalate to project lead
- May require architecture review
- Decision documented in ADR

### Process
1. Parties present positions
2. Project lead facilitates discussion
3. Decision made and documented
4. Move forward respectfully

## Communication Channels

### Public
- **GitHub Issues**: Bugs, feature requests, discussions
- **GitHub Discussions**: Open technical discussions
- **Pull Requests**: Code contributions and review

### Security
- **Vulnerabilities**: Report privately via GitHub (see [SECURITY.md](./SECURITY.md))
- **Response time**: < 24 hours for critical

## Code Review Standards

### Review Checklist
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Type annotations complete
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No import boundary violations
- [ ] No security vulnerabilities
- [ ] No unnecessary dependencies

### Expected Timeline
- Simple fixes: 1-2 days
- Features: 3-5 days
- Large changes: 1-2 weeks

## Maintenance

### Repository Maintenance
- Keep dependencies updated
- Address security vulnerabilities immediately
- Monitor test results
- Track technical debt

### Documentation Maintenance
- README.md kept current
- API docs regenerated: `make docs`
- Examples updated with releases
- ADRs maintained

### Performance
- Monitor test execution time
- Address performance regressions
- Profile and optimize as needed

## Escalation Path

For decisions or conflicts:

1. **Reviewer** — Code-level decisions in pull request review
2. **Maintainers** — Review disputes, process questions
3. **Project Leads** — Architectural decisions, unresolved conflicts

---

## Questions?

- **Governance questions**: Open a GitHub issue or discussion
- **Technical questions**: Discuss in GitHub Discussions
- **Security concerns**: Report via GitHub (see [SECURITY.md](./SECURITY.md))

---

**Last Updated**: 2026-08-21  
**Status**: Active
