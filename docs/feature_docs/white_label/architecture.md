# White Label Module Architecture

## Overview
Supports branding per restaurant (themes, logos, domains).

## System Flow
- Tenant config loaded on login
- Custom theme/assets applied
- Email/SMS headers customized
- Analytics scoped to brand

## Key Components
- Theme Loader
- Tenant Config Manager
- Custom Asset Engine
- Brand Router

## Developer Notes
Each component should follow service-layer design with unit test coverage.
