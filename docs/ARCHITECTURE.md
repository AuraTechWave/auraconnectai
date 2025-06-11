# AuraConnect Architecture

## Overview
AuraConnect is composed of modular services that operate independently but interact over REST APIs and shared databases.

## Services
- **Backend**: Auth, Orders, Inventory, Payroll
- **Frontend**: Admin dashboard, reports
- **Mobile**: Manager interface, offline-ready

## DevOps
- Docker Compose for local dev
- PostgreSQL for data persistence
- GitHub Actions for CI/CD
