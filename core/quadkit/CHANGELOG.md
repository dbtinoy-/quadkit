# Changelog

All notable changes to this package will be documented in this file.

This project follows:
- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/)

---

## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 

### Deprecated
- 

---

## [1.2.0] - 2026-04-25

### Added
- New `CacheProvider` for Redis backend
- Support for async streaming responses

### Changed
- Improved container resolution performance (~20%)
- Updated logging format to include request IDs

### Fixed
- Fixed circular dependency detection edge case
- Fixed memory leak in scoped container

---

## [1.1.0] - 2026-03-10

### Added
- Introduced `Result[T, E]` helpers (`map`, `and_then`)
- Added health check support in providers

### Changed
- Refactored provider lifecycle ordering

---

## [1.0.0] - 2026-01-01

### Added
- Initial release
- Dependency Injection container
- Provider system
- Module system

---

## Types of Changes

- **Added** → new features  
- **Changed** → changes in existing functionality  
- **Fixed** → bug fixes  
- **Removed** → removed features  
- **Deprecated** → soon-to-be removed features  