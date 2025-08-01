# AuraConnect Documentation

Welcome to the AuraConnect documentation. This guide will help you understand, deploy, and contribute to the AuraConnect restaurant management platform.

## 📚 Documentation Structure

### Core Documentation
- **[System Architecture](architecture/README.md)** - Comprehensive system design and technical architecture
- **[API Documentation](http://localhost:8000/docs)** - Interactive API documentation (when running locally)
- **Production Deployment Guide (see source code)** - Step-by-step production deployment

### Module Documentation

#### 🍔 Restaurant Operations
- **[Order Management](dev/architecture/order_management_architecture.md)** - Real-time order processing system
- **[Menu & Inventory](dev/architecture/menu_inventory_architecture.md)** - Dynamic menu and inventory management
- **[Kitchen Integration](feature_docs/README.md)** - Kitchen display and workflow optimization

#### 💰 Financial Management
- **[Payroll System](feature_docs/payroll/README.md)** - Comprehensive payroll processing
  - [Architecture](feature_docs/payroll/architecture.md)
  - [Tax Calculation Flow](feature_docs/payroll/tax_calculation_flow.md)
- **[Tax Services](feature_docs/tax/README.md)** - Multi-jurisdiction tax compliance
  - [Architecture](feature_docs/tax/architecture.md)

#### 👥 Staff Management
- **[Staff Management](dev/architecture/staff_management_architecture.md)** - Employee lifecycle management
- **[Attendance Tracking](dev/architecture/staff_management_architecture.md)** - Time and attendance system

#### 🔌 Integrations
- **[POS Integration](feature_docs/pos_integration/README.md)** - Multi-POS system support
  - [Architecture](feature_docs/pos_integration/architecture.md)
- **[Offline Sync](feature_docs/offline_sync/README.md)** - Offline-first architecture
  - [Architecture](feature_docs/offline_sync/architecture.md)

#### 🤖 Advanced Features
- **[AI Agents](feature_docs/ai_agents/README.md)** - AI-powered automation
  - [Architecture](feature_docs/ai_agents/architecture.md)
- **[Analytics & Reporting](dev/architecture/analytics_reporting_architecture.md)** - Business intelligence
- **[Customer Loyalty](dev/architecture/customer_loyalty_architecture.md)** - Loyalty program management

#### 🏢 Enterprise Features
- **[White Labeling](feature_docs/white_label/README.md)** - Multi-tenant white label support
  - [Architecture](feature_docs/white_label/architecture.md)
- **[Compliance](feature_docs/compliance/README.md)** - Regulatory compliance framework
  - [Architecture](feature_docs/compliance/architecture.md)

### Development Documentation
- **[CI/CD Setup](dev/CI_CD_SETUP.md)** - Continuous integration and deployment
- **[Development Guide](dev/README.md)** - Developer setup and guidelines
- **[Global Architecture Overview](dev/architecture/global_architecture_overview.md)** - High-level system overview

## 🚀 Getting Started

### For Developers
1. Start with the [System Architecture](architecture/README.md) to understand the overall design
2. Set up your development environment following the main [README](../README.md)
3. Explore module-specific documentation based on your area of work

### For DevOps Engineers
1. Review the Production Deployment Guide (see source code)
2. Check the [CI/CD Setup](dev/CI_CD_SETUP.md) for automation
3. Understand the [System Architecture](architecture/README.md) for infrastructure planning

### For Product Managers
1. Explore feature-specific documentation in the [feature_docs](feature_docs/) directory
2. Review the [Global Architecture Overview](dev/architecture/global_architecture_overview.md)
3. Check module architectures for capability understanding

## 📖 Key Concepts

### Architecture Principles
- **Modular Monolith**: Self-contained modules with clear boundaries
- **Domain-Driven Design**: Business logic encapsulated in services
- **API-First**: RESTful APIs with OpenAPI documentation
- **Event-Driven**: Webhook system for integrations

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 14+
- **Cache**: Redis 7+
- **Container**: Docker & Docker Compose
- **Authentication**: JWT with refresh tokens

## 🔍 Finding Information

### By Feature
- Browse the [feature_docs](feature_docs/) directory for feature-specific documentation
- Each feature has a README and architecture document

### By Module
- Check the [dev/architecture](dev/architecture/) directory for module-specific architectures
- Core modules: Orders, Staff, Payroll, Tax, POS

### By Topic
- **Security**: See [System Architecture](ARCHITECTURE.md#security-architecture)
- **Performance**: See [System Architecture](ARCHITECTURE.md#performance-architecture)
- **Deployment**: See Production Deployment Guide (see source code)

## 🤝 Contributing

When adding new documentation:
1. Place feature documentation in `feature_docs/[feature_name]/`
2. Add architecture documents in `dev/architecture/`
3. Update this README with links to new documentation
4. Follow the existing documentation structure and style

## 📞 Support

- **GitHub Issues**: Report bugs and request features
- **API Documentation**: Available at `/docs` when running the application
- **Architecture Questions**: Refer to [ARCHITECTURE.md](architecture/README.md)

---

<div align="center">
  📚 Keep documentation up-to-date as the system evolves
</div>