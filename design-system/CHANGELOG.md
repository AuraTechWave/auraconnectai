# Changelog

All notable changes to the AuraConnect Design System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-08-19

### Added
- Initial release of AuraConnect Design System
- Design tokens for colors, typography, spacing, shadows, borders, and animations
- Light and dark theme support with automatic switching
- Component specifications for 8 core components:
  - Button (contained, outlined, text variants)
  - Card (elevated, outlined, filled variants)
  - Table (with sorting, filtering, pagination)
  - Tabs (standard, pills, vertical variants)
  - Input (text fields and textareas)
  - Select (dropdowns with multi-select support)
  - Modal (dialog with focus management)
  - Notification (alerts, toasts, snackbars)
- WCAG 2.1 AA compliant color combinations
- Accessibility guidelines and requirements
- React component examples with full ARIA support
- CSS output with CSS variables
- TypeScript definitions
- Build pipeline with Style Dictionary
- Theme customization and white-labeling support
- Comprehensive documentation

### Security
- Input sanitization for custom themes
- Restricted white-label overrides to prevent code injection

## [1.0.1] - 2025-08-19

### Fixed
- Removed Node.js dependencies from client-side code (resolver.js)
- Added robust error handling to CSS extraction script
- Created separate client-side validator module for browser compatibility
- Added fallback mechanisms for missing theme files
- Improved error messages and logging throughout build process
- Added deep merge functionality for theme overrides
- Fixed regex escaping in client-side validation code

### Security
- Isolated theme validation logic to prevent runtime errors in browsers
- Enhanced sanitization for font family values

## Unreleased

### Planned
- Additional component specifications (Tooltip, Accordion, DatePicker)
- RTL support
- Enhanced motion design tokens
- Figma plugin integration
- Storybook setup
- Visual regression testing
- Additional theme presets