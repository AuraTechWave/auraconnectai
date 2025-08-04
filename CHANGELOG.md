# Changelog

All notable changes to AuraConnect will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed - Breaking Documentation Changes
- **BREAKING**: Complete documentation restructure - all documentation URLs have changed
  - Moved from flat structure to organized hierarchy under `/docs`
  - All module documentation now under `/docs/modules/`
  - Feature documentation consolidated under `/docs/feature_docs/`
  - Architecture documentation moved to `/docs/architecture/` and `/docs/dev/architecture/`
  - API documentation centralized at `/docs/api/`
  - Previous documentation URLs will no longer work
- Migrated documentation from custom structure to MkDocs with Material theme
- Added comprehensive navigation structure in `mkdocs.yml`
- Improved documentation organization with clear separation of concerns

### Added
- New comprehensive README.md with system overview and quick navigation
- Detailed module documentation for Orders, Menu, and Staff modules
- Architecture overview documentation
- Getting started guide for developers
- Deployment guide with multiple deployment options
- API reference documentation
- Developer personas guide for role-specific documentation paths
- Status badges for documentation, CI/CD, and license
- Table of contents for long documentation files
- MkDocs configuration with Material theme for better documentation site
- Mermaid diagram support for architecture visualizations

### Fixed
- Fixed all broken internal documentation links
- Removed references to non-existent backend/frontend files in docs
- Resolved MkDocs strict mode build warnings
- Fixed anchor links and cross-references

### Removed
- Removed outdated roadmap documentation
- Removed duplicate README files
- Removed broken links to external implementation files

## [2.0.0] - 2025-01-15

### Added
- Phase 6: Documentation & Integration for Payroll & Tax Module (AUR-308)
- Kitchen print ticket system (AUR-268)
- POS-initiated Order Sync for Bidirectional Integration (AUR-272)
- Special Instructions Workflow for Order Management (AUR-267)
- Customer notes and attachments for Order Management (AUR-266)
- Fraud detection checkpoints for Order Management system (AUR-265)

### Changed
- Enhanced payroll module with comprehensive tax calculation
- Improved order management with advanced workflow features
- Updated POS integration for bidirectional synchronization

### Fixed
- Various bug fixes and performance improvements
- Security enhancements in authentication system

## [1.0.0] - 2024-10-01

### Added
- Initial release of AuraConnect platform
- Core modules: Orders, Menu, Staff, Inventory
- Basic authentication and authorization
- Multi-tenant support
- RESTful API with OpenAPI documentation
- Docker containerization support

[Unreleased]: https://github.com/AuraTechWave/auraconnectai/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/AuraTechWave/auraconnectai/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/AuraTechWave/auraconnectai/releases/tag/v1.0.0